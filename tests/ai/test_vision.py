import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from zaldi.ai.vision import describe_image
from zaldi.errors import ValidationError

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_returns_single_line_tags():
    llm = FakeListChatModel(responses=["red silk saree,\n gold zari border,  wedding"])
    assert describe_image(PNG, "image/png", llm) == "red silk saree, gold zari border, wedding"


def test_image_is_sent_as_data_uri():
    seen = []

    class Spy(FakeListChatModel):
        def _generate(self, messages, *a, **k):
            seen.append(messages[0].content)
            return super()._generate(messages, *a, **k)

    describe_image(PNG, "image/png", Spy(responses=["kurta"]))
    assert seen[0][1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("data, mime", [(PNG, "application/pdf"), (b"", "image/png"), (b"x" * (5 * 1024 * 1024 + 1), "image/png")])
def test_invalid_uploads_rejected(data, mime):
    with pytest.raises(ValidationError):
        describe_image(data, mime, FakeListChatModel(responses=["x"]))
