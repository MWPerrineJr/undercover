import { label } from "./format";
import type { QueueRun } from "./types";

export function TodoList({
  progress,
}: Readonly<{ progress: QueueRun | null }>) {
  if (!progress?.run_id) return null;
  return (
    <section className="todos" aria-label="The agent's to-do list">
      <div className="section-heading">
        <h3>To-do list</h3>
        <span className="queue-count">{progress.todos.length}</span>
      </div>
      {progress.todos.length === 0 ? (
        <p className="muted">The agent is planning this run.</p>
      ) : (
        <ol className="todo-list">
          {progress.todos.map((todo) => (
            <li key={todo.claim_id} className={`todo ${todo.state}`}>
              <span className="todo-top">
                <span className="identifier">{todo.claim_id}</span>
                <span className={`badge ${todo.state}`}>
                  {label(todo.state)}
                </span>
              </span>
              <strong>{todo.title}</strong>
              {todo.note && <span className="todo-note">{todo.note}</span>}
            </li>
          ))}
        </ol>
      )}
      {progress.summary && <p className="queue-summary">{progress.summary}</p>}
    </section>
  );
}
