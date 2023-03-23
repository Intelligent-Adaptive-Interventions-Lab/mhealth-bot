from typing import List, Dict, Optional, Tuple
import openai
import os
import re
import json
import time

openai.organization = "org-FYH4qiS0WzXH7l0pCbezhmat"

class Answer:
    """
    This is an Answer Class contains awll of the answer choices and data.
    """
    
    TYPE = "type"
    CHOICES = "choices"
    DESC = "description"

    def __init__(self, question: str, answer_information: Dict=None, auxillary_data: {}={}) -> None:

        if not answer_information:
            return

        self.type = answer_information.get(self.TYPE, None)
        self.choices = answer_information.get(self.CHOICES, None)
        self.description = answer_information.get(self.DESC, None)
        self.question = question
        self.quality_analysis_level = 2
        self.default_quality_analysis_level = 2
        self.auxillary_data = auxillary_data

    def __str__(self) -> str:

        return f"[ANSWER]: type: {self.type}, choices: {self.choices}, description: {self.description}"

    def check_answer(self, answer: str=None, condition: Dict={}) -> bool:
        if not condition or not answer:
            return True


        if self.type == "likert":
            avaliable_choices = self.get_choices()
            # conditions: ["gt", "lt", "gte", "lte", "eqt", "any"]
            for k, v in condition.items():
                if k == "gt":
                    avaliable_choices = list(filter(lambda value: value > v, avaliable_choices))
                elif k == "lt":
                    avaliable_choices = list(filter(lambda value: value < v, avaliable_choices))
                elif k == "gte":
                    avaliable_choices = list(filter(lambda value: value >= v, avaliable_choices))
                elif k == "lte":
                    avaliable_choices = list(filter(lambda value: value <= v, avaliable_choices))
                elif k == "eqt":
                    avaliable_choices = list(filter(lambda value: value == v, avaliable_choices))

            return self.format_answer(answer) in avaliable_choices

        if self.type == "free-text":
            self.quality_analysis_level = self.default_quality_analysis_level

            check_pass = True
            # conditions: ["eqt", "contains", "any"]
            for k, v in condition.items():
                if k == "eqt":
                    check_pass &= isinstance(v, str) and self.format_answer(answer) == v
                elif k == "contains":
                    check_pass &= isinstance(v, list) and any([text in self.format_answer(answer) for text in v])
                elif k == "contains_all":
                    check_pass &= isinstance(v, list) and all([text in self.format_answer(answer) for text in v])
                elif k == "contains_one":
                    check_pass &= (isinstance(v, list) or isinstance(v, dict)) and ([text in self.format_answer(answer) for text in v].count(True) == 1)

                    if check_pass and isinstance(v, dict):
                        for mapping in v.items():
                            if mapping[0] in self.format_answer(answer):
                                self.auxillary_data[mapping[1]] = mapping[0]
                elif k == "save_as" and isinstance(v, str):
                    self.auxillary_data[v] = answer 
                elif k == "set_quality_analysis" and isinstance(v, int):
                    self.quality_analysis_level = v


            return check_pass

        return False

    def validate_answer(self, answer: str=None) -> Tuple[bool, Optional[str]]:

        if self.type == "likert":
            if not answer or not answer.isnumeric():
                return False, self.description

            if self.format_answer(answer) in self.choices:
                return True, None
            return False, self.description

        if self.type == "free-text":

            ans = self.format_answer(answer)

            if ans == "":
                return False, 'Your answer cannot be empty.'

            if self.choices:
                if ans in self.choices:
                    return True, None
                else:
                    return False, 'Please answer according to the choices.'

            try:
                if self.quality_analysis_level >= 1:
                    is_english_query = openai.Completion.create(
                        model="text-davinci-003",
                        prompt=f"Is the text english? Yes or No?\n\nText: {ans}\n\nAnswer:",
                        temperature=0,
                    )['choices'][0]['text'].lower().strip()

                    if "no" in is_english_query:
                        print('NOT ENGLISH')
                        return False, f"Sorry, I don't understand."

                if self.quality_analysis_level >= 2:
                    variables = list(set(re.findall("\[\S*\]", self.question)))
                    for var in variables:
                        self.question = self.question.replace(var, self.auxillary_data.get(var, "___"))

                    is_relevant_answer_query = openai.Completion.create(
                        model="text-davinci-003",
                        prompt=f"Give a rating for the answer out of 10 in terms of how well it answers the question and follows its instructions. Rate strictly. Give the rating then explain why in a caring tone."
                        f"\n\nQuestion: {self.question}\n\nAnswer: {ans}\n\nResult: ",
                        temperature=0,
                        max_tokens=100
                    )['choices'][0]['text'].strip()

                    print(is_relevant_answer_query)

                    result = re.search("([0-9]).*10([\s\S]*)", is_relevant_answer_query)
                    rating = result.group(1)
                    response = result.group(2).strip()

                    if (int(rating) < 8):
                        return False, response

            except Exception as e:
                print(e)

            # return False, f"Here is the message again.\n\n{self.question}"

        return True, None

    def format_answer(self, answer: str=None):

        if self.type == "likert":
            return float(answer)

        if self.type == "free-text":
            return answer.lower().strip()

        return answer

    def get_choices(self) -> List:

        return self.choices

    def get_description(self) -> str:

        return self.description


class Dialog:
    """
    This is a Dialog Class contains all of the logics including answer choices, 
    dialogue redirections, messages, etcs.
    """

    ID = "dialogue_id"
    MESSAGE = "bot_message"
    ANSWER = "answer"
    JUMPTO = "jump_to"

    def __init__(self, dialogue_information: Dict, auxillary_data: {}={}) -> None:

        if not dialogue_information.get(self.ID, None):
            return

        self.auxillary_data = auxillary_data
        self.id = dialogue_information.get(self.ID, None)
        self.message = dialogue_information.get(self.MESSAGE, None)

        self.jumpto = dialogue_information.get(self.JUMPTO, None)

        if dialogue_information.get(self.ANSWER, None):
            self.answer = Answer(self.message, dialogue_information.get(self.ANSWER, None), auxillary_data=auxillary_data)
        else:
            self.answer = None

    def __str__(self) -> str:

        return self.id

    def get_id(self) -> str:

        return self.id

    def get_message(self) -> List[str]:
        variables = list(set(re.findall("\[\S*\]", self.message)))
        for var in variables:
            self.message = self.message.replace(var, self.auxillary_data.get(var, "___"))

        messages = [self.message]
        if self.answer and self.answer.get_description():
            messages.append(self.answer.get_description())

        return messages

    def get_answer(self) -> Optional[Answer]:

        return self.answer

    def get_jumpto(self) -> Optional[Dict]:

        return self.jumpto

    def validate_answer(self, answer: str) -> Tuple[bool, Optional[str]]:
        if not self.answer:
            return True, None

        return self.answer.validate_answer(answer)


class DialogCollection:
    """
    This is a DialogCollection Class contains all Dialogs.
    """

    def __init__(self, dialogues: List[Dict], answers: Dict={}, auxillary_data: {}={}) -> None:
        self.auxillary_data = auxillary_data
        self.answers = answers
        self.dialogues = {}

        for d in dialogues:
            self.dialogues[d.get("dialogue_id")] = Dialog(d, auxillary_data=auxillary_data)

        self.curr_id = dialogues[0].get("dialogue_id")

    def move_to_question(self) -> Tuple[str, List[str]]:
        curr_dialogue = self.dialogues.get(self.curr_id)
        messages = curr_dialogue.get_message()

        jumpto_conditions = curr_dialogue.get_jumpto()
        if not jumpto_conditions:
            return self.curr_id, messages

        jumpto_cond = jumpto_conditions[0]
        next_id = jumpto_cond.get("to")

        if not next_id:
            return self.curr_id, messages

        if curr_dialogue.get_answer() is None:
            self.curr_id = next_id
            _, next_messages = self.move_to_question()
            return self.curr_id, messages + next_messages

        return self.curr_id, messages

    def move_to_next(self, show_current: bool=False) -> Tuple[str, List[str]]:

        curr_dialogue = self.dialogues.get(self.curr_id)

        messages = []


        jumpto_conditions = curr_dialogue.get_jumpto()
        if not jumpto_conditions:
            return self.curr_id, messages

        for jumpto_cond in jumpto_conditions:
            conditions = jumpto_cond.get("conditions")
            next_id = jumpto_cond.get("to")

            print(f"CONDITIONS: {conditions}")
            print(f"NEXT ID: {next_id}")

            condition_pass = True
            for selected_condition in conditions or []:

                target = selected_condition.get("target", self.curr_id)
                condition = selected_condition.get("condition")

                target_dialogue = self.dialogues.get(target)
                target_answer = self.answers.get(target, None)

                print(f"TARGET ANSWER: {target_answer}")
                print(f"CONDITION: {condition}")

                print(f"ANSWER: {target_dialogue.get_answer().check_answer(target_answer, condition)}")
                condition_pass &= target_dialogue.get_answer().check_answer(target_answer, condition)

            if condition_pass:
                if show_current:
                    messages = curr_dialogue.get_message()
                else:
                    messages = []
                    curr_answer = self.answers.get(self.curr_id, None)
                    is_valid, answer_description = curr_dialogue.validate_answer(curr_answer)
                    if (answer_description and not answer_description[0].isalpha()):
                        answer_description = answer_description[1:]

                    if not is_valid:
                        return self.curr_id, filter(lambda x: x!=None, [answer_description, "Please try again."])

                self.curr_id = next_id
                _, next_messages = self.move_to_question()
                return self.curr_id, messages + next_messages
            # else:
            #     return self.curr_id, ["Your answer did not meet the requirements of the question."]

        # return self.curr_id, messages
        return self.curr_id, ["Your answer did not meet the requirements of the question."]

    def get_num_dialogues(self) -> int:

        return len(self.dialogues.items())

    def get_curr_id(self) -> str:

        return self.curr_id

    def get_curr_messages(self) -> List[str]:

        return self.dialogues[self.curr_id].get_message()

    def set_curr_id(self, id: str) -> None:

        self.curr_id = id

    def add_answer(self, answer: str) -> None:

        self.answers[self.curr_id] = answer


if __name__ == "__main__":

    with open('./static/dialogues/mindfulness.json') as file:
        curr_dialogues = json.load(file)

    dialog_collection = DialogCollection(curr_dialogues)

    print(dialog_collection.move_to_next(show_current=True)) 

    print(dialog_collection.add_answer("1")) # BAP20003
    print(dialog_collection.move_to_next(show_current=False))

    print(dialog_collection.add_answer("1")) # BAP20004
    print(dialog_collection.move_to_next(show_current=False))

    print(dialog_collection.add_answer("1")) # BAP20005
    print(dialog_collection.move_to_next(show_current=False))

    print(dialog_collection.add_answer("1")) # BAP20006
    print(dialog_collection.move_to_next(show_current=False))

    print(dialog_collection.add_answer("7")) # BAP20007
    print(dialog_collection.move_to_next(show_current=False))

    print(dialog_collection.add_answer("leaves on the stream")) # BAP20011
    print(dialog_collection.move_to_next(show_current=False))

    print(dialog_collection.answers)