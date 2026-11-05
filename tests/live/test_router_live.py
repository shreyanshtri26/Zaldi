from zaldi.ai.router import Route
from zaldi.services.chat_service import get_router


def test_routes_product_and_chitchat_messages():
    router = get_router()  # shared and cached: building it costs ~90 embedding calls
    assert router.guide("Do you have Banarasi sarees under 10000 rupees?") is Route.PRODUCTS
    assert router.guide("What's your favorite movie?") is Route.CHITCHAT
