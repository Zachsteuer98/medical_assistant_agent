from types import SimpleNamespace

from app.rag.llm import OpenAIChatModel


class _Recorder:
    def __init__(self):
        self.messages = None

    def create(self, **kwargs):
        self.messages = kwargs["messages"]
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))])


def _model() -> tuple[OpenAIChatModel, _Recorder]:
    model = OpenAIChatModel("test-key", "http://localhost", "m", 0.0, 10, 1.0)
    recorder = _Recorder()
    model._client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    return model, recorder


def test_empty_system_prompt_sends_only_user_message():
    model, rec = _model()
    model.complete("", "hi")
    assert rec.messages == [{"role": "user", "content": "hi"}]


def test_system_prompt_is_sent_first():
    model, rec = _model()
    model.complete("sys", "hi")
    assert [m["role"] for m in rec.messages] == ["system", "user"]
