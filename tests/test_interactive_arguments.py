import argparse

from aimes_cli.interactive import complete_required_arguments


def _parser():
    parser = argparse.ArgumentParser(prog="aimes")
    sub = parser.add_subparsers(dest="command", required=True)
    configure = sub.add_parser("configure")
    configure.add_argument("--tools", required=True, choices=["codex-cli", "claude-code"])
    repair = sub.add_parser("repair")
    repair.add_argument("repair_id")
    repair.add_argument("--confirm", required=True)
    return parser


def test_prompts_for_missing_required_option_and_validates_choices():
    answers = iter(["wrong", "codex-cli"])
    messages = []
    result = complete_required_arguments(
        _parser(),
        ["configure"],
        input_fn=lambda prompt: next(answers),
        output_fn=messages.append,
    )
    assert result == ["configure", "--tools", "codex-cli"]
    assert any("输入无效" in message for message in messages)


def test_prompts_for_required_nested_positional_and_option():
    answers = iter(["repair-123", "APPLY-FIX"])
    result = complete_required_arguments(
        _parser(),
        ["repair"],
        input_fn=lambda prompt: next(answers),
    )
    assert result == ["repair", "repair-123", "--confirm", "APPLY-FIX"]


def test_does_not_prompt_for_values_already_supplied():
    result = complete_required_arguments(
        _parser(),
        ["configure", "--tools", "claude-code"],
        input_fn=lambda prompt: (_ for _ in ()).throw(AssertionError("unexpected prompt")),
    )
    assert result == ["configure", "--tools", "claude-code"]


def test_q_cancels_argument_collection():
    try:
        complete_required_arguments(
            _parser(),
            ["configure"],
            input_fn=lambda prompt: "Q",
        )
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError("expected interactive cancellation")
