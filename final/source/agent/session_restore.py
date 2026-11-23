"""What a restart does to a Session loaded from the State Store: nothing re-runs.

A task that was in progress is ended: logged paused `interrupted`, the code-built message is
sent as the error event and added to the conversation, then it is cancelled so nothing is left
to Retry. A plan's running step instead fails with its report, through the shared task end. A
Confirmation that was open is expired. The Shopper asks again; no action is replayed.
"""

from agent.session_state import Session
from agent.task_runtime import TaskRuntime

_IN_PROGRESS = {"interpreting", "awaiting_action_result", "awaiting_answer"}


def interrupted_message(language: str) -> str:
    if language == "ar":
        return "انقطعت المهمة بسبب إعادة تشغيل. اطلبها تاني."
    return "This task was interrupted by a restart. Please ask again."


def restore_interrupted(runtime: TaskRuntime, session: Session) -> None:
    task = session.active_task
    if task is None or task.status not in _IN_PROGRESS:
        return
    if task.status == "awaiting_answer" and task.mutation_kind is not None:
        # The single-use Confirmation was never stored: it is expired, not carried over.
        runtime.record(
            session,
            "confirmation",
            task_id=task.task_id,
            outcome="expired",
            mutation_kind=task.mutation_kind,
        )
    session.requires_reconciliation = False
    message = interrupted_message(task.language)
    runtime.end_task(session, task, "paused", "interrupted", message)
    if session.active_task is task:
        # Not a plan step (a plan's end already reported and cancelled the task): the task is
        # over, not kept for Retry, which could repeat a change that already happened. The
        # Shopper reads the message in the conversation and simply asks again.
        session.conversation.append({"role": "copilot", "text": message})
        runtime.end_task(session, task, "cancelled")
