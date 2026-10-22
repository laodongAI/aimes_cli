"""Interactive completion for missing required AIMES CLI arguments.

The normal argparse interface remains authoritative. This helper only collects
missing required values in a TTY; non-interactive automation keeps standard
argparse behavior.
"""
from __future__ import annotations

import argparse
from typing import Sequence


def _walk_parsers(parser: argparse.ArgumentParser):
    """Yield parser and all nested command parsers."""
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for child in action.choices.values():
                yield from _walk_parsers(child)


def complete_required_arguments(
    parser: argparse.ArgumentParser,
    argv: Sequence[str],
    *,
    input_fn=input,
    output_fn=print,
) -> list[str]:
    """Prompt for omitted required options/positionals and return augmented argv.

    Existing arguments are never replaced. Choices and argparse type converters
    are validated before a value is accepted. Entering q/cancel aborts collection.
    """
    args = list(argv)
    parsers = list(_walk_parsers(parser))
    saved = []
    try:
        # Temporarily relax required checks so argparse can identify the selected
        # nested command even when some of its required arguments are missing.
        for current in parsers:
            for action in current._actions:
                saved.append((action, getattr(action, "required", None), action.nargs))
                if isinstance(action, argparse._SubParsersAction):
                    action.required = False
                elif action.option_strings and getattr(action, "required", False):
                    action.required = False
                elif not action.option_strings and action.nargs is None:
                    action.nargs = "?"
        namespace, unknown = parser.parse_known_args(args)
        if unknown:
            return args

        selected = []
        current = parser
        while True:
            selected.append(current)
            sub_action = next((a for a in current._actions if isinstance(a, argparse._SubParsersAction)), None)
            if sub_action is None:
                break
            command = getattr(namespace, sub_action.dest, None)
            if not command or command not in sub_action.choices:
                break
            current = sub_action.choices[command]

        for current in selected:
            for action in current._actions:
                is_required_option = bool(action.option_strings and any(
                    old_required for old_action, old_required, _ in saved if old_action is action
                ))
                original_nargs = next((old_nargs for old_action, _, old_nargs in saved if old_action is action), action.nargs)
                is_required_positional = not action.option_strings and original_nargs is None and action.dest != argparse.SUPPRESS
                if not (is_required_option or is_required_positional):
                    continue
                existing = getattr(namespace, action.dest, None)
                # An explicitly supplied optional may have a non-None default; do
                # not prompt for it. Required values that are absent are None.
                if existing is not None:
                    continue
                if action.dest in ("help",):
                    continue
                prompt = action.option_strings[-1] if action.option_strings else action.dest.replace("_", " ")
                if action.help and action.help is not argparse.SUPPRESS:
                    prompt += f" — {action.help}"
                while True:
                    value = input_fn(f"请补充参数 {prompt}（输入 q 取消）：").strip()
                    if value.casefold() in {"q", "quit", "cancel", "取消"}:
                        raise KeyboardInterrupt
                    if not value:
                        output_fn("此参数为必填项，请输入有效值。")
                        continue
                    try:
                        if action.choices is not None and value not in action.choices:
                            raise ValueError("可选值：" + ", ".join(map(str, action.choices)))
                        if action.type is not None:
                            action.type(value)
                        break
                    except (ValueError, argparse.ArgumentTypeError) as exc:
                        output_fn(f"输入无效：{exc}，请重新输入。")
                if action.option_strings:
                    args.extend([action.option_strings[0], value])
                else:
                    args.append(value)
                # Reparse after each answer so subsequent required values in
                # mutually exclusive/nested contexts are resolved correctly.
                namespace, unknown = parser.parse_known_args(args)
        return args
    finally:
        for action, required, nargs in reversed(saved):
            if required is not None:
                action.required = required
            action.nargs = nargs
