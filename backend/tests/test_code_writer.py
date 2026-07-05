from unittest.mock import patch

from app.domain.agents.code_writer import CodeWriterAgent
from app.domain.state.workflow_state import WorkflowStateSchema
from app.services.llm_service import TruncatedLLMResponseError


def _state(targets: list[str]) -> WorkflowStateSchema:
    return WorkflowStateSchema(
        task_id=1,
        issue_url="https://github.com/o/r/issues/1",
        repo_url="https://github.com/o/r",
        plan={"files_to_modify": targets, "changes": ["fix"]},
        repo_files=[{"path": p, "content": f"// {p}\n"} for p in targets],
    )


def test_code_writer_batches_multiple_targets():
    agent = CodeWriterAgent()
    state = _state(["a.ts", "b.ts", "c.ts"])
    calls: list[list[str]] = []

    def fake_batch(self, st, batch_paths):
        calls.append(list(batch_paths))
        return {p: f"// updated {p}\n" for p in batch_paths}

    with patch.object(CodeWriterAgent, "_write_batch", fake_batch):
        agent.run(state)

    assert calls == [["a.ts"], ["b.ts"], ["c.ts"]]
    assert set(state.generated_code.keys()) == {"a.ts", "b.ts", "c.ts"}


def test_code_writer_retries_truncated_batch_one_file_at_a_time():
    agent = CodeWriterAgent()
    state = _state(["a.ts", "b.ts"])
    calls: list[list[str]] = []

    def fake_batch(self, st, batch_paths):
        calls.append(list(batch_paths))
        if len(batch_paths) > 1:
            raise TruncatedLLMResponseError("truncated")
        return {batch_paths[0]: f"// updated {batch_paths[0]}\n"}

    with patch.object(CodeWriterAgent, "_write_batch", fake_batch):
        agent.run(state)

    assert calls == [["a.ts"], ["b.ts"]]
    assert state.generated_code["a.ts"].startswith("// updated")
