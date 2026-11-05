from zaldi.db import chat_log_repo, init_db
from zaldi.services.chat_service import handle_query


def test_product_question_is_answered_and_logged(temp_db):
    init_db()
    result = handle_query("Which sarees do you have under Rs. 2000?")
    assert result["type"] == "products" and result["response"]
    assert chat_log_repo.stats()["chats"] == 1
