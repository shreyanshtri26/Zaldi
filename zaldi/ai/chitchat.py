"""Small-talk chain used when the router decides a message is not about products or policies."""
from langchain_core.prompts import PromptTemplate

from zaldi.ai.prompts import get_prompt


def create_chitchat_chain(llm):
    return PromptTemplate.from_template(get_prompt("chitchat")) | llm
