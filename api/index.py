from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
import psycopg2
import os


POSTGRES_URL = os.environ.get("POSTGRES_URL")

def get_db_connection():
    return psycopg2.connect(POSTGRES_URL)

# --- FastAPI App ---
app = FastAPI()

@app.get("/")
def root():
    return {"message": "Hello from FastAPI on Vercel!"}

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://construct-pro-frontend.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class Task(BaseModel):
    id: Optional[int] = None
    name: str
    assigned_to: str
    deadline: Optional[date] = None
    priority: str
    progress: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class TaskUpdate(BaseModel):
    name: Optional[str] = None
    assigned_to: Optional[str] = None
    deadline: Optional[date] = None
    priority: Optional[str] = None
    progress: Optional[int] = None

# --- Helper Functions ---
def row_to_task(row):
    return Task(
        id=row[0],
        name=row[1],
        assigned_to=row[2],
        deadline=row[3],
        priority=row[4],
        progress=row[5],
        created_at=str(row[6]) if row[6] else None,
        updated_at=str(row[7]) if row[7] else None
    )

# --- Health Check Endpoint ---
@app.get("/")
def health_check():
    return {"status": "API is running"}

# --- API Endpoints ---
@app.get("/tasks", response_model=List[Task])
def get_tasks():
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, assigned_to, deadline, priority, progress, created_at, updated_at
                FROM tasks ORDER BY id DESC;
            """)
            rows = cursor.fetchall()
            return [row_to_task(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/tasks", response_model=Task)
def add_task(task: Task):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO tasks (name, assigned_to, deadline, priority, progress)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, name, assigned_to, deadline, priority, progress, created_at, updated_at;
            """, (
                task.name, task.assigned_to, task.deadline, task.priority, task.progress
            ))
            row = cursor.fetchone()
            conn.commit()
            return row_to_task(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/tasks/{task_id}/progress", response_model=Task)
def update_task_progress(task_id: int, progress: int):
    if progress < 0 or progress > 100:
        raise HTTPException(status_code=400, detail="Progress must be between 0 and 100")
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE tasks
                SET progress = %s
                WHERE id = %s
                RETURNING id, name, assigned_to, deadline, priority, progress, created_at, updated_at;
            """, (progress, task_id))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            conn.commit()
            return row_to_task(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task_update: TaskUpdate):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            set_clause = []
            params = []
            if task_update.name is not None:
                set_clause.append("name = %s")
                params.append(task_update.name)
            if task_update.assigned_to is not None:
                set_clause.append("assigned_to = %s")
                params.append(task_update.assigned_to)
            if task_update.deadline is not None:
                set_clause.append("deadline = %s")
                params.append(task_update.deadline)
            if task_update.priority is not None:
                set_clause.append("priority = %s")
                params.append(task_update.priority)
            if task_update.progress is not None:
                if task_update.progress < 0 or task_update.progress > 100:
                    raise HTTPException(status_code=400, detail="Progress must be between 0 and 100")
                set_clause.append("progress = %s")
                params.append(task_update.progress)
            if not set_clause:
                raise HTTPException(status_code=400, detail="No fields to update")
            params.append(task_id)
            query = f"""
                UPDATE tasks
                SET {', '.join(set_clause)}
                WHERE id = %s
                RETURNING id, name, assigned_to, deadline, priority, progress, created_at, updated_at;
            """
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            conn.commit()
            return row_to_task(row)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM tasks WHERE id = %s RETURNING id;", (task_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Task not found")
            conn.commit()
            return {"message": "Task deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
