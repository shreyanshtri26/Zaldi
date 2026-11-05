import pytest

from zaldi.db import content_repo, init_db
from zaldi.errors import ValidationError
from zaldi.services import cart
from zaldi.services.cart_chat import handle_cart_message, parse_intent

S = "sess-1"


@pytest.fixture(autouse=True)
def db(temp_db):
    init_db()


def pid(name_part):
    return next(p["id"] for p in content_repo.list_rows("products") if name_part in p["product_name"])


def test_pricing_shipping_threshold():
    kurti = next(p for p in content_repo.list_rows("products") if p["price"] < 900 and p["stock_quantity"] > 0)
    c = cart.add_item(S, kurti["id"])
    assert c["subtotal"] == kurti["price"] and c["shipping"] == 79 and c["total"] == kurti["price"] + 79
    assert c["free_shipping_gap"] == 999 - kurti["price"]
    saree = pid("Banarasi")
    c = cart.add_item(S, saree)
    assert c["shipping"] == 0 and c["total"] == c["subtotal"]


def test_empty_cart_has_no_shipping():
    c = cart.get_cart(S)
    assert c["items"] == [] and c["total"] == 0 and c["shipping"] == 0


def test_add_merges_and_quantity_capped_by_stock():
    p = pid("Banarasi")
    content_repo.update_row("products", p, {"stock_quantity": 3})
    cart.add_item(S, p, 2)
    assert cart.add_item(S, p)["items"][0]["quantity"] == 3
    with pytest.raises(ValidationError, match="only 3"):
        cart.add_item(S, p)


def test_out_of_stock_and_unknown_product_rejected():
    p = pid("Banarasi")
    content_repo.update_row("products", p, {"stock_quantity": 0})
    with pytest.raises(ValidationError, match="out of stock"):
        cart.add_item(S, p)
    with pytest.raises(ValidationError):
        cart.add_item(S, 99999)
    with pytest.raises(ValidationError):
        cart.add_item(S, pid("Chikankari"), 0)


def test_set_quantity_remove_clear_and_isolation_between_sessions():
    a, b = pid("Chikankari"), pid("Banarasi")
    cart.add_item(S, a)
    cart.add_item("other", b)
    assert cart.set_quantity(S, a, 3)["items"][0]["quantity"] == 3
    assert cart.set_quantity(S, a, 0)["items"] == []
    with pytest.raises(ValidationError):
        cart.set_quantity(S, a, 2)  # not in cart
    assert len(cart.get_cart("other")["items"]) == 1
    assert cart.clear_cart("other")["items"] == []


def test_coupon():
    cart.add_item(S, pid("Banarasi"))
    c = cart.apply_coupon(S, "welcome10")
    assert c["discount"] == round(c["subtotal"] * 0.1) and c["total"] == c["subtotal"] - c["discount"]
    with pytest.raises(ValidationError):
        cart.apply_coupon(S, "FREEMONEY")


def test_price_change_is_reflected_live():
    p = pid("Banarasi")
    cart.add_item(S, p)
    content_repo.update_row("products", p, {"price": 1000})
    assert cart.get_cart(S)["subtotal"] == 1000


@pytest.mark.parametrize("text, action, ordinal, qty", [
    ("add the first one to my cart", "add", 1, 1),
    ("add the 2nd kurta to cart", "add", 2, 1),
    ("put the last one in my bag", "add", -1, 1),
    ("add 3 of the second one", "add", 2, 3),
    ("remove the saree from my cart", "remove", None, 1),
    ("show my cart", "show", None, 1),
    ("what is in my cart", "show", None, 1),
    ("empty my cart", "clear", None, 1),
    ("change the quantity to 4", "set_quantity", None, 4),
    ("apply WELCOME10", "coupon", None, 1),
])
def test_intent_parsing(text, action, ordinal, qty):
    i = parse_intent(text)
    assert (i.action, i.ordinal, i.quantity) == (action, ordinal, qty)


def test_chat_add_by_position_after_search_then_show_and_remove():
    ids = [pid("Banarasi"), pid("Chikankari")]
    cart.remember_results(S, ids)
    r = handle_cart_message(S, "add the second one to my cart")
    assert "Chikankari" in r["response"] and r["cart"]["item_count"] == 1
    assert "Chikankari" in handle_cart_message(S, "show my cart")["response"]
    r = handle_cart_message(S, "remove the chikankari kurta")
    assert r["cart"]["items"] == []


def test_chat_add_by_name_without_prior_search():
    r = handle_cart_message(S, "add the banarasi silk saree to my cart")
    assert r["cart"]["items"] and "Banarasi" in r["cart"]["items"][0]["product_name"]


def test_chat_ambiguous_reference_asks_instead_of_guessing():
    r = handle_cart_message(S, "add it to my cart")
    assert "couldn't tell" in r["response"] and r["cart"]["items"] == []


def test_chat_errors_become_messages():
    p = pid("Banarasi")
    content_repo.update_row("products", p, {"stock_quantity": 0})
    cart.remember_results(S, [p])
    assert "out of stock" in handle_cart_message(S, "add the first one")["response"]
    assert "not a valid coupon" in handle_cart_message(S, "apply code SAVE50")["response"]
    assert "couldn't tell" in handle_cart_message(S, "remove the first one")["response"]  # cart is empty
