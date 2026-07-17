import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_usage_eval as harness


class UsageHarnessTests(unittest.TestCase):
    def test_viewport_review_labels_each_local_action(self):
        case = {
            "id": "fixture",
            "rubric": ["Preserve the result."],
            "controls": ["next", "go deeper"],
        }
        run = harness.ParsedRun(
            "thread-1",
            {field: 0 for field in harness.USAGE_FIELDS},
            1,
            ("Initial.", "Second.", "Expanded.", "Complete."),
        )

        review = harness.render_review(case, {"viewport": run})

        self.assertIn("Transparent viewport action transcript", review)
        self.assertIn("### Initial viewport", review)
        self.assertIn("### After “next”", review)
        self.assertIn("### After “go deeper”", review)
        self.assertIn("### After “full”", review)

    def test_parse_jsonl_extracts_thread_messages_and_usage(self):
        text = "\n".join(
            (
                json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "Useful answer."},
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "mcp_tool_call",
                            "tool": "create_answer_capsule",
                            "result": {
                                "structured_content": {
                                    "session_id": "11111111-1111-1111-1111-111111111111"
                                }
                            },
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 40,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                        },
                    }
                ),
            )
        )

        parsed = harness.parse_jsonl(text)

        self.assertEqual(parsed.thread_id, "thread-1")
        self.assertEqual(parsed.assistant_messages, ("Useful answer.",))
        self.assertEqual(parsed.usage_events, 1)
        self.assertEqual(parsed.usage["input_tokens"], 100)
        self.assertEqual(parsed.usage["reasoning_output_tokens"], 5)
        self.assertEqual(len(parsed.mcp_tool_calls), 1)
        self.assertEqual(
            harness.capsule_session_id(parsed),
            "11111111-1111-1111-1111-111111111111",
        )

    def test_combine_runs_sums_each_usage_field(self):
        first = harness.ParsedRun(
            "thread-1",
            {
                "input_tokens": 10,
                "cached_input_tokens": 2,
                "output_tokens": 3,
                "reasoning_output_tokens": 1,
            },
            1,
            ("one",),
        )
        second = harness.ParsedRun(
            None,
            {
                "input_tokens": 20,
                "cached_input_tokens": 10,
                "output_tokens": 4,
                "reasoning_output_tokens": 2,
            },
            1,
            ("two",),
        )

        combined = harness.combine_runs((first, second))

        self.assertEqual(combined.thread_id, "thread-1")
        self.assertEqual(combined.usage_events, 2)
        self.assertEqual(combined.usage["input_tokens"], 30)
        self.assertEqual(combined.usage["cached_input_tokens"], 12)
        self.assertEqual(combined.assistant_messages, ("one", "two"))

    def test_combine_runs_rejects_different_threads(self):
        empty_usage = {field: 0 for field in harness.USAGE_FIELDS}
        first = harness.ParsedRun("thread-1", empty_usage, 1, ())
        second = harness.ParsedRun("thread-2", empty_usage, 1, ())
        with self.assertRaises(ValueError):
            harness.combine_runs((first, second))

    def test_cost_uses_uncached_cached_and_output_rates(self):
        usage = {
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "output_tokens": 20,
            "reasoning_output_tokens": 5,
        }
        rates = {
            "input_per_million": 1.0,
            "cached_input_per_million": 0.5,
            "output_per_million": 2.0,
        }

        self.assertAlmostEqual(harness.estimated_cost_usd(usage, rates), 0.00012)

    def test_aggregate_reports_total_and_median_ratios(self):
        def summary(baseline_total, parsnip_total):
            def condition(total, turns):
                return {
                    "usage": {
                        "input_tokens": total,
                        "cached_input_tokens": 0,
                        "output_tokens": 0,
                        "reasoning_output_tokens": 0,
                    },
                    "assistant_turns": turns,
                    "local_navigation_calls": 0,
                }

            ratios = {
                name: {"reported_token_ratio": total / baseline_total}
                for name, total in (
                    ("ordinary", parsnip_total + 10),
                    ("parsnip", parsnip_total),
                    ("buffered", baseline_total + 5),
                    ("lean_buffered", baseline_total + 1),
                )
            }
            return {
                "baseline": condition(baseline_total, 1),
                "ordinary": condition(parsnip_total + 10, 2),
                "parsnip": condition(parsnip_total, 2),
                "buffered": condition(baseline_total + 5, 1),
                "lean_buffered": condition(baseline_total + 1, 1),
                "ratios": ratios,
            }

        aggregate = harness.aggregate_summaries(
            (summary(100, 100), summary(100, 200), summary(100, 300)),
            ("baseline", "ordinary", "parsnip", "buffered", "lean_buffered"),
        )

        self.assertEqual(aggregate["total_reported_token_ratio"], 2.0)
        self.assertEqual(aggregate["median_case_reported_token_ratio"], 2.0)
        self.assertEqual(aggregate["baseline_assistant_turns"], 3)
        self.assertEqual(aggregate["parsnip_assistant_turns"], 6)
        self.assertEqual(
            aggregate["conditions"]["buffered"]["reported_token_total"], 315
        )

    def test_aggregate_can_report_only_baseline_and_capture(self):
        def condition(total):
            return {
                "usage": {
                    "input_tokens": total,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_output_tokens": 0,
                },
                "assistant_turns": 1,
                "local_navigation_calls": 3,
            }

        summaries = (
            {
                "baseline": condition(100),
                "capture": condition(105),
                "ratios": {"capture": {"reported_token_ratio": 1.05}},
            },
            {
                "baseline": condition(100),
                "capture": condition(115),
                "ratios": {"capture": {"reported_token_ratio": 1.15}},
            },
        )
        aggregate = harness.aggregate_summaries(
            summaries, ("baseline", "capture")
        )

        self.assertEqual(aggregate["capture_reported_token_total"], 220)
        self.assertEqual(aggregate["capture_total_reported_token_ratio"], 1.1)
        self.assertEqual(
            aggregate["capture_median_case_reported_token_ratio"], 1.1
        )
        self.assertEqual(
            aggregate["conditions"]["capture"]["local_navigation_calls"], 6
        )

    def test_private_output_rejects_repository_paths(self):
        repo = harness.repository_root()
        with self.assertRaises(ValueError):
            harness.require_private_output(repo / ".dogfood-private", repo)

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                harness.require_private_output(Path(directory), repo),
                Path(directory).resolve(),
            )

    def test_commands_use_json_and_resume_the_same_thread(self):
        repo = harness.repository_root()
        start = harness.build_start_command(
            "codex", repo, "prompt", "model-x", ephemeral=True
        )
        resume = harness.build_resume_command(
            "codex", "thread-1", "next", "model-x"
        )

        self.assertIn("--json", start)
        self.assertIn("--ephemeral", start)
        self.assertEqual(start[-1], "prompt")
        self.assertEqual(resume[-2:], ["thread-1", "next"])

    def test_parsnip_locator_uses_the_canonical_source(self):
        prompt = harness.attach_parsnip_locator("task", harness.repository_root())
        self.assertIn("[$parsnip:parsnip]", prompt)
        self.assertIn("plugins/parsnip/skills/parsnip/SKILL.md", prompt)
        self.assertTrue(prompt.endswith("task"))

    def test_progressive_and_buffer_prompts_are_explicit(self):
        parsnip = harness.ORDINARY_PREFIX + "teach the task"
        ordinary = harness.ordinary_progressive_prompt(parsnip)
        buffered = harness.buffered_prompt(parsnip)
        lean = harness.lean_buffered_prompt(parsnip)

        self.assertIn("exactly two content controls", ordinary)
        self.assertNotIn("linked Parsnip skill", ordinary)
        self.assertIn("create_answer_capsule exactly once", buffered)
        self.assertIn("requery_triggers", buffered)
        self.assertIn("create_lean_answer_capsule", lean)
        self.assertIn("Do not read skills", lean)
        self.assertNotIn("final synthesis", lean.lower().replace("duplicate final synthesis", ""))

    def test_buffer_actions_and_cli_are_local(self):
        repo = harness.repository_root()
        command = harness.build_buffer_cli_command(
            repo, "11111111-1111-1111-1111-111111111111", "full"
        )

        self.assertEqual(harness.normalize_buffer_action("go deeper"), "more")
        self.assertEqual(harness.normalize_buffer_action("full answer"), "full")
        self.assertEqual(command[0], "/bin/sh")
        self.assertIn("plugins/parsnip/mcp/launch.sh", command[1])
        self.assertEqual(command[-3:], ["navigate", command[-2], "full"])

    def test_capture_commands_are_explicit_and_local_navigation_is_separate(self):
        repo = harness.repository_root()
        start = harness.build_capture_run_command(
            repo, Path("/tmp/request.md"), "model-x", 90
        )
        navigate = harness.build_capture_navigation_command(
            repo, "11111111-1111-1111-1111-111111111111", "next"
        )

        self.assertIn("--allow-model-call", start)
        self.assertIn("--model", start)
        self.assertIn("model-x", start)
        self.assertIn("90000", start)
        self.assertIn("--target-output-tokens", start)
        self.assertIn("450", start)
        self.assertIn("--effort", start)
        self.assertIn("none", start)
        self.assertEqual(navigate[-3], "navigate")
        self.assertEqual(navigate[-1], "next")

    def test_viewport_reuses_baseline_and_has_only_local_commands(self):
        repo = harness.repository_root()
        ingest = harness.build_viewport_file_command(
            repo, Path("/tmp/baseline-response.md")
        )
        self.assertEqual(ingest[-2:], ["viewport-file", "/tmp/baseline-response.md"])
        retained = harness.build_viewport_file_command(
            repo,
            Path("/tmp/baseline-response.md"),
            "thread-1",
            resumable=True,
        )
        routed = harness.build_capture_route_command(
            repo,
            "11111111-1111-1111-1111-111111111111",
            "go deeper naturally",
        )
        self.assertEqual(retained[-4:], ["--thread-id", "thread-1", "--resumable", "true"])
        self.assertEqual(routed[-2:], ["11111111-1111-1111-1111-111111111111", "go deeper naturally"])

        cases = harness.load_cases(Path(__file__).with_name("usage_cases.json"))
        parser = harness.build_parser()
        args = parser.parse_args(
            [
                "--case",
                cases[0]["id"],
                "--condition",
                "baseline",
                "--condition",
                "viewport",
                "--dry-run",
            ]
        )
        args.conditions = harness.select_conditions(args.condition_ids)
        plan = harness.dry_run_commands(
            [cases[0]], args, harness.repository_root()
        )[0]
        self.assertEqual(plan["selected_conditions"], ["baseline", "viewport"])
        self.assertIn("baseline", plan)
        self.assertEqual(
            plan["viewport_source"], "Reuse the exact baseline final answer"
        )
        self.assertIn("viewport-file", plan["viewport_ingest"])
        self.assertNotIn("--ephemeral", plan["baseline"])
        self.assertIn("viewport_natural_requests", plan)
        self.assertIn("route", plan["viewport_natural_requests"][0])
        self.assertIn(cases[0]["controls"][0], plan["viewport_natural_requests"][0])
        self.assertNotIn("viewport_start", plan)

    def test_adaptive_viewport_dry_run_retains_and_reenters_one_thread(self):
        cases = harness.load_cases(Path(__file__).with_name("usage_cases.json"))
        parser = harness.build_parser()
        args = parser.parse_args(
            [
                "--case",
                "planning-repair-cafe",
                "--condition",
                "baseline",
                "--condition",
                "adaptive_viewport",
                "--model",
                "model-x",
                "--dry-run",
            ]
        )
        args.conditions = harness.select_conditions(args.condition_ids)

        plan = harness.dry_run_commands(
            [case for case in cases if case["id"] == "planning-repair-cafe"],
            args,
            harness.repository_root(),
        )[0]

        self.assertNotIn("--ephemeral", plan["baseline"])
        self.assertIn("--resumable true", plan["adaptive_viewport_ingest"])
        self.assertEqual(len(plan["adaptive_natural_requests"]), 2)
        self.assertTrue(
            all("reenter" in command for command in plan["adaptive_natural_requests"])
        )
        self.assertTrue(
            all("--allow-model-call" in command for command in plan["adaptive_natural_requests"])
        )

    def test_ordinary_followup_dry_run_uses_the_same_retained_baseline(self):
        cases = harness.load_cases(Path(__file__).with_name("usage_cases.json"))
        parser = harness.build_parser()
        args = parser.parse_args(
            [
                "--case",
                "planning-repair-cafe",
                "--condition",
                "baseline",
                "--condition",
                "adaptive_viewport",
                "--condition",
                "ordinary_followup",
                "--dry-run",
            ]
        )
        args.conditions = harness.select_conditions(args.condition_ids)
        plan = harness.dry_run_commands(
            [case for case in cases if case["id"] == "planning-repair-cafe"],
            args,
            harness.repository_root(),
        )[0]

        self.assertEqual(
            plan["selected_conditions"],
            ["baseline", "adaptive_viewport", "ordinary_followup"],
        )
        self.assertNotIn("--ephemeral", plan["baseline"])
        self.assertIn("--resumable true", plan["ordinary_followup_ingest"])
        self.assertEqual(len(plan["ordinary_followup_natural_requests"]), 2)
        self.assertTrue(
            all(
                "--ordinary-followup" in command
                for command in plan["ordinary_followup_natural_requests"]
            )
        )

    def test_dry_run_can_reuse_a_private_completed_baseline(self):
        cases = harness.load_cases(Path(__file__).with_name("usage_cases.json"))
        with tempfile.TemporaryDirectory() as directory:
            baseline = Path(directory) / "baseline.jsonl"
            baseline.write_text("{}\n", encoding="utf-8")
            parser = harness.build_parser()
            args = parser.parse_args(
                [
                    "--case",
                    cases[0]["id"],
                    "--condition",
                    "baseline",
                    "--condition",
                    "viewport",
                    "--reuse-baseline-jsonl",
                    str(baseline),
                    "--dry-run",
                ]
            )
            args.conditions = harness.select_conditions(args.condition_ids)
            plan = harness.dry_run_commands(
                [cases[0]], args, harness.repository_root()
            )[0]
            self.assertEqual(plan["baseline"], f"Reuse {baseline}")

    def test_capture_usage_requires_complete_app_server_accounting(self):
        result = {
            "status": "section",
            "section": {"content": "First safe block."},
            "source": {"thread_id": "thread-capture"},
            "capture_usage": {
                "input_tokens": 100,
                "cached_input_tokens": 40,
                "output_tokens": 20,
                "reasoning_output_tokens": 5,
            },
        }
        parsed = harness.parsed_capture_start(result)
        self.assertEqual(parsed.thread_id, "thread-capture")
        self.assertEqual(parsed.usage_events, 1)
        self.assertEqual(parsed.usage["cached_input_tokens"], 40)
        self.assertEqual(parsed.assistant_messages, ("First safe block.",))

        broken = dict(result)
        broken["capture_usage"] = None
        with self.assertRaises(RuntimeError):
            harness.parsed_capture_start(broken)

    def test_condition_selection_requires_paired_baseline(self):
        self.assertEqual(
            harness.select_conditions(("capture", "baseline")),
            ("baseline", "capture"),
        )
        with self.assertRaises(ValueError):
            harness.select_conditions(("capture",))

    def test_dry_run_can_isolate_baseline_and_capture(self):
        cases = harness.load_cases(Path(__file__).with_name("usage_cases.json"))
        parser = harness.build_parser()
        args = parser.parse_args(
            [
                "--case",
                cases[0]["id"],
                "--condition",
                "baseline",
                "--condition",
                "capture",
                "--dry-run",
            ]
        )
        args.conditions = harness.select_conditions(args.condition_ids)
        plan = harness.dry_run_commands([cases[0]], args, harness.repository_root())[0]
        self.assertEqual(plan["selected_conditions"], ["baseline", "capture"])
        self.assertIn("baseline", plan)
        self.assertIn("capture_start", plan)
        self.assertNotIn("ordinary_start", plan)
        self.assertNotIn("parsnip_start", plan)

    def test_repository_cases_are_valid_and_cover_release_categories(self):
        cases = harness.load_cases(Path(__file__).with_name("usage_cases.json"))
        self.assertEqual(len(cases), 5)
        self.assertEqual(
            {case["category"] for case in cases},
            {"debugging", "planning", "learning", "document-review", "decision"},
        )


if __name__ == "__main__":
    unittest.main()
