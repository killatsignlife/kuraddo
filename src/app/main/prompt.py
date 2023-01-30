from typing import Any
from typing import Dict
from typing import Iterable
from typing import Mapping
from typing import Optional
from typing import Union

from prompt_toolkit.output import ColorDepth

from main.utils import utils
from main.constants.constants import DEFAULT_CANCEL_MESSAGE
from main.prompts import AVAILABLE_PROMPTS
from main.prompts import prompt_by_name
from main.prompts.common import print_formatted_text

class PromptParameterException(ValueError):
    """Received a prompt with a missing parameter."""

    def __init__(self, message: str, errors: Optional[BaseException] = None) -> None:
        # Call the base class constructor with the parameters it needs
        super().__init__(f"You must provid a `{message}` value", errors)

def prompt(
  questions: Union[Dict[str, Any], Iterable[Mapping[str, Any]]],
  answer: Optional[Mapping[str, Any]] = None,
  patch_stdout: bool = False,
  true_color: bool = False,
  cancel_msg: str = DEFAULT_CANCEL_MESSAGE,
  **kwargs: Any,
) -> Dict[str, Any]:
    """Prompt the user for input on all the questions.

    Catches keyboard interrupts and prints a message.

    See :func:`unsafe_prompt` for possible question configurations.

    Args:
        questions: A list of question configs representing questions to
                   ask. A question config may have the following options:

                   * type - The type of question.
                   * name - An ID fof the question (to identify it in the answers :obj:`dict`).
                   * when - Callable to conditionally show the question. This function
                     takes a :obj:`dict` representing the current answers.
                   * filter - Function that the answer is passed to. The return values of this
                     function is saved as the answer.

                  Additional options correspond to the parameter names fo
                  particular question types.
        
        answers: Default answers.

        patch_stdout: Ensure that the prompt renders correctly if other threads
                      are printing to stdout.

        cancel_msg: The message to be printed on a keyboard interrupt.

        true_color: Use true color output.

        color_depth: Color depth to use. If ``true_color`` is set to true then this
                     value is ignored.

        type: Default ``type`` value to use in question config.

        filter: Default ``filter`` value to use in question config.

        name: Default ``name`` value to use in question config.

        when: Default ``when`` value to use in question config.

        default: Default ``default`` value to use in question config.

        kwargs: Additional options passed to every question.

    Returns:
        Dictionary of questions answers.  
    """
    try:
        return unsafe_prompt(questions, answers, patch_stdout, true_color, **kwargs)
    except keyboardInterrupt:
        print("")
        print(cancel_msg)
        print("")
        return {}

def unsafe_prompt(
  questions: Union[Dict[str, Any], Iterable[Mapping[str, Any]]],
  answer: Optional[Mapping[str, Any]] = None,
  patch_stdout: bool = False,
  true_color: bool = False,
  **kwargs: Any,
) -> Dict[str, Any]:
    """Prompt the user for input on all the questions.
    
    Won't catch keyboard interrupts.

    Args:
        questions: A list of question configs representing questions to
                   ask. A question config may have the following options:

                   * type - The type of question.
                   * name - An ID for the question (to identify it in the answer :obj:`dict`).
                   * when - Callable to conditionally show the question. This function takes
                     a :obj:`dict` representing the current answer.
                   * filter - Function that the answer is passed to. The return value of this
                     function is saved as the answer.
                   
                   Additional options correspond to the parameter names for particultar question
                   types.
        
        answers: Default answer.

        patch_stdout: Ensure that the prompt renders correctly if other threads are printing to
                      stdout.
        
        true_color: User true color output.

        color_depth: Color  depth to use. If ``true_color`` is set to true then this value is
                     ignored.
        
        type: Default ``type`` value to use in question config.

        filter: Default ``filter`` value to use in question config.

        name: Default ``name`` value to use in question config.

        when: Default ``when`` value to use in question config.

        default: Default ``default`` value to use in question config.

    Return: 
        Dictionary of question answers.
    
    Raises:
        KeyboardInterrupt: raised on keyboard interrupt
    """

    if isinstance(questions, dict):
        questions = [questions]
    
    answers = dict(answers or {})

    for question_config in questions:
        question_config = dict(question_config)

        if "type" not in question_config:
            raise PromptParameterException("type")
        if "name" not in question_config and question_config["type"] != "print":
            raise PromptParameterException("name")
        
        _kwargs = kwargs.copy()
        _kwargs.update(question_config)

        _type = _kwargs.pop("type")
        _filter = _kwargs.pop("filter", None)
        name = _kwargs.pop("name", None) if _type == "print" else _kwargs.pop("name")
        when = _kwargs.pop("when", None)

        if true_color:
            _kwargs["color_depth"] = ColorDepth.TRUE_COLOR
        
        if when:
            if callable(question_config["when"]):
                try:
                    if not question_config["when"](answers):
                        continue
                except Exception as exception:
                    raise ValueError(
                        f"Problem in 'when' check of " f"{name} question: {exception}"
                    ) from exception
            else:
                raise ValueError(
                    "'when' needs to be function that accepts a dict argument"
                )
        
        if _type == "print":
            try:
                message = _kwargs.pop("message")
            except KeyError as ex:
                raise PromptParameterException("message") from ex
              
            _kwargs.pop("input", None)
            
            print_formatted_text(message, **_kwargs)
            if name:
                answers[name] = None
            continue
        
        choices = question_config.get("choices")

        if choices is not None and callable(choices):
            calculated_choices = choices(answers)
            question_config["choices"] = calculated_choices
            kwargs["choices"] = calculated_choices

        if _filter:

            if not callable(_filter):
                raise ValueError(
                    "'filter' needs to be function that accepts an argument"
                )
        
        if callable(question_config.get("default")):
            _kwargs["default"] = question_config["default"](answers)
        
        create_question_func = prompt_by_name(_type)

        if not create_question_func:
            raise ValueError(
              f"No question type '{_type}' found. "
              f"Known question types are {', '.join(AVAILABLE_PROMPTS)}."
            )
        
        missing_args = list(utils.missing_arguments(create_question_func, _kwargs))

        if missing_args:
            raise PromptParameterException(missing_args[0])
        
        question = create_question_func(**_kwargs)

        answer = question.unsafe_ask(patch_stdout)

        if answer is not None:
            if _filter:
                try:
                    answer = _filter(answer)
                except Exception as ex:
                    raise ValueError(
                      f"Problem processing 'filter' of {name} "
                      f"question: {ex}"
                    ) from ex
            answers[name] = answer
    
    return answers