# Smart Classroom & Laboratory Allocation System — Backend

A modular, production-minded backend for automated constraint-based classroom and laboratory allocation in educational institutions. The application automatically assigns optimal rooms to scheduled classes while respecting room capacities, specialized facility requirements, availability, timetable constraints, and department-specific laboratory access policies. It also handles ad-hoc bookings, maintenance scheduling, dynamic re-optimization, and efficiency metrics benchmarking.

---

## Table of Contents

1. [Architecture & Design](#1-architecture--design)
2. [Technology Stack](#2-technology-stack)
3. [Prerequisites](#3-prerequisites)
4. [Environment Setup & Installation](#4-environment-setup--installation)
5. [Database Configuration & Migrations](#5-database-configuration--migrations)
6. [Seed Data & Pre-configured Scenarios](#6-seed-data--pre-configured-scenarios)
7. [Running the Application](#7-running-the-application)
8. [Running Tests](#8-running-tests)
9. [Optimization Engine (Google OR-Tools CP-SAT)](#9-optimization-engine-google-or-tools-cp-sat)
10. [Efficiency Metrics & Baseline Benchmarking](#10-efficiency-metrics--baseline-benchmarking)
11. [REST API Documentation & Examples](#11-rest-api-documentation--examples)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Architecture & Design

The backend is built as a layered modular monolith following clean architecture principles and separation of concerns:

```
Client (Next.js / Swagger UI / HTTP Client)
       │
       ▼
 FastAPI Routers (`app/api/routes/`)
       │
       ▼
 Pydantic Schemas (`app/schemas/`)  <-- Input Validation & Serialization
       │
       ▼
 Service Layer (`app/services/`)    <-- Business Logic, State Transitions & Mutexes
       │
       ├──► OR-Tools Optimization Engine (`app/optimizer/`)
       │         ├── CP-SAT Mathematical Model & Hard/Soft Constraints
       │         ├── Independent Result Validator (`result_validator.py`)
       │         └── First-Fit Baseline Benchmarker (`solver.py`)
       │
       ▼
 Repository Layer (`app/repositories/`) <-- Reusable SQLAlchemy Queries
       │
       ▼
 Database Engine (`app/database/`) & Models (`app/models/`)
       │
       ▼
 Persistent Storage (PostgreSQL / SQLite)
```

### Core Business Rules Enforced

* **Shared Regular Classrooms**: Regular classrooms (`room_type: CLASSROOM`) are shared across all departments. Their eligibility never depends on department ownership.
* **Strict Laboratory Access**: Laboratories (`room_type: LAB`) restrict access exclusively to explicitly authorized departments via `room_department_access`. An unconfigured lab has zero authorized departments and cannot be assigned to any department until authorized. Configuring lab access on a regular classroom is rejected.
* **Non-Overlapping Intervals**: Two intervals overlap if and only if `existing_start < requested_end AND requested_start < existing_end`. Adjacent intervals (where one begins exactly when the previous ends) are valid.
* **Concurrency Protection**: To prevent double-bookings during simultaneous requests, the service layer employs room-level transactional mutexes and PostgreSQL row-level locks (`SELECT ... FOR UPDATE`).
* **Maintenance & Unavailability Safeguards**: Creating room downtime checks for future confirmed bookings and published allocations, requiring explicit authorized resolution (`force=true`).
* **Two-Phase Timetable Publishing**: Allocations are produced in `DRAFT` status. Publishing re-validates the schedule against the live database state to prevent publishing stale or invalidated allocations.

---

## 2. Technology Stack

* **Language**: Python 3.12+ (tested and verified on Python 3.12, 3.13, 3.14)
* **API Framework**: FastAPI 0.143+
* **ASGI Server**: Uvicorn
* **Data Validation**: Pydantic v2 & Pydantic-Settings
* **ORM & Persistence**: SQLAlchemy 2.x
* **Migrations**: Alembic 1.20+
* **Optimization Engine**: Google OR-Tools CP-SAT 9.15+
* **Database**: PostgreSQL (production default) & SQLite (local development/testing)
* **Testing**: PyTest & HTTPX / Starlette TestClient
* **Security & Auth**: Bcrypt password hashing & PyJWT token handling

---

## 3. Prerequisites

* Python 3.12 or compatible Python version.
* (Optional for local dev, required for prod) PostgreSQL 15+ database instance.
* Git.

---

## 4. Environment Setup & Installation

### Step 1: Clone and Navigate to the Backend Directory

```bash
cd backend
```

### Step 2: Create and Activate Virtual Environment

```bash
# On macOS / Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Adjust variables in `.env` as needed:

```ini
APP_ENV=development
API_V1_PREFIX=/api/v1
PROJECT_NAME="Smart Classroom Allocation System"

# For PostgreSQL:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/classroom_allocation

# For SQLite (instant zero-configuration local setup):
DATABASE_URL=sqlite:///./classroom_allocation.db

SECRET_KEY=development-secret-key-at-least-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FRONTEND_ORIGIN=http://localhost:3000

SOLVER_TIME_LIMIT_SECONDS=30.0
SOLVER_RANDOM_SEED=42
SOLVER_NUM_WORKERS=4
```

---

## 5. Database Configuration & Migrations

### If Using PostgreSQL

1. Create the database:
   ```bash
   createdb -U postgres classroom_allocation
   ```
2. Set `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/classroom_allocation` in your `.env`.

### Run Alembic Migrations

To apply database migrations to the latest revision:

```bash
alembic upgrade head
```

To create a new migration after model changes:

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

---

## 6. Seed Data & Pre-configured Scenarios

The seed script creates realistic departments, buildings, classrooms, labs, facilities, class groups, sessions, and default users.

To seed the database:

```bash
python scripts/seed_data.py
```

### Included Entities & Scenarios

1. **Departments**: `CSE`, `ECE`, `MECH`.
2. **Classrooms**:
   * `Room 101` (Capacity: 40, Projector)
   * `Room 102` (Capacity: 60, Projector, Smart Board)
   * `Room 201` (Capacity: 80, Projector)
3. **Laboratories**:
   * `CSE Computer Lab` (Capacity: 35, Authorized: CSE)
   * `Electronics Lab` (Capacity: 30, Authorized: ECE)
   * `Shared Computer Lab` (Capacity: 40, Authorized: CSE, ECE)
4. **Scenarios Pre-loaded**:
   * **Feasible Scenario**: Regular classes fit neatly into Room 102 and Room 201 without conflict.
   * **Lab Authorization Scenario**: CSE and ECE labs assigned only to their authorized departments.
   * **Contention Scenario**: Multiple large classes (70+ students) competing for the single large lecture hall (Room 201).
   * **Infeasible Lab Scenario**: MECH class requesting a lab when MECH has no authorized laboratory.
   * **Reallocation Scenario**: Dynamic re-optimization when a room experiences emergency maintenance.
5. **Default Admin Account**:
   * Username: `admin`
   * Password: `admin123`

---

## 7. Running the Application

Start the development server with hot-reload enabled:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive documentation will be available at:
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **API Base URL**: `http://localhost:8000/api/v1`

---

## 8. Running Tests

The test suite runs against an isolated, in-memory SQLite database (`StaticPool`) ensuring no developer data is modified or destroyed.

Run all tests:

```bash
pytest -v
```

Run a specific test module:

```bash
pytest tests/test_allocations.py -v
pytest tests/test_bookings.py -v
```

---

## 9. Optimization Engine (Google OR-Tools CP-SAT)

The optimization engine utilizes Google OR-Tools CP-SAT solver (`ortools.sat.python.cp_model`) to perform constraint satisfaction and combinatorial optimization.

### Decision Variable
For each scheduled session $i$ and eligible room $j$:
$$x_{i, j} \in \{0, 1\}$$
where $x_{i, j} = 1$ if session $i$ is assigned to room $j$, else $0$.

### Hard Constraints
1. **At Most One Room Per Session**:
   $$\text{unallocated}_i + \sum_{j \in \text{Eligible}(i)} x_{i, j} = 1$$
2. **Room Interval Non-Overlapping**:
   For any two sessions $i_1, i_2$ assigned to room $j$ with overlapping intervals:
   $$x_{i_1, j} + x_{i_2, j} \le 1$$
3. **Class Group Interval Non-Overlapping**:
   A student class group cannot attend overlapping sessions simultaneously:
   $$\sum_j x_{i_1, j} + \sum_j x_{i_2, j} \le 1$$
4. **Room Capacity**: $x_{i, j} = 0$ if $\text{Capacity}(j) < \text{StudentCount}(i)$.
5. **Room Type**: $x_{i, j} = 0$ if $\text{RoomType}(j) \ne \text{RequiredType}(i)$.
6. **Required Facilities**: $x_{i, j} = 0$ if $\text{RequiredFacilities}(i) \not\subseteq \text{RoomFacilities}(j)$.
7. **Lab Authorization**: $x_{i, j} = 0$ if $\text{RoomType}(j) = \text{LAB}$ and $\text{Department}(i) \notin \text{AuthorizedDepts}(j)$.
8. **Maintenance & Confirmed Bookings**: Excluded from variables if time blocks intersect.

### Soft Constraints & Multi-Objective Function
$$\min \left( W_{\text{unalloc}} \sum_i \text{unallocated}_i + W_{\text{waste}} \sum_{i, j} (\text{Capacity}_j - \text{Students}_i) x_{i, j} + W_{\text{perturb}} \sum_i \text{Changed}(i) \right)$$
* $W_{\text{unalloc}} = 100,000$: Maximizing total allocated classes is the highest priority.
* $W_{\text{waste}} = 2$: Minimizing unused excess seats.
* $W_{\text{perturb}} = 500$: Minimizing schedule disruptions during dynamic reallocation.

### Independent Result Validator
Before any solution is persisted, the `AllocationResultValidator` independently verifies the assignment against all hard constraints, guaranteeing that even if a model edge-case occurs, no invalid timetable is ever stored or published.

---

## 10. Efficiency Metrics & Baseline Benchmarking

The system evaluates both the CP-SAT optimizer and a greedy **First-Fit Baseline** algorithm on the exact same input dataset:

1. **Allocation Rate**:
   $$\frac{\text{Allocated Sessions}}{\text{Total Eligible Sessions}} \times 100\%$$
2. **Seat Utilization**:
   $$\frac{\sum \text{Students Assigned}}{\sum \text{Assigned Room Capacity}} \times 100\%$$
3. **Room Occupancy Rate**:
   $$\frac{\text{Unique Rooms Used}}{\text{Total Active Rooms}} \times 100\%$$
4. **Room Conflict Count**: Must be strictly $0$.
5. **Class Schedule Conflict Count**: Must be strictly $0$.
6. **Solver Runtime (ms)**: Measured execution time.
7. **Assignments Changed**: Count of altered assignments during dynamic re-allocation.

---

## 11. REST API Documentation & Examples

All application endpoints are prefixed with `/api/v1`.

### A. Health & Diagnostics
* `GET /api/v1/health`
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "service": "Smart Classroom Allocation System API"
  }
  ```

### B. Departments
* `POST /api/v1/departments`
  ```json
  // Request
  { "name": "Mechanical Engineering", "code": "MECH" }
  // Response (201 Created)
  {
    "id": 3,
    "name": "Mechanical Engineering",
    "code": "MECH",
    "created_at": "2026-10-09T12:00:00Z",
    "updated_at": "2026-10-09T12:00:00Z"
  }
  ```
* `GET /api/v1/departments`
* `GET /api/v1/departments/{id}`
* `PATCH /api/v1/departments/{id}`
* `DELETE /api/v1/departments/{id}`

### C. Classrooms & Labs
* `POST /api/v1/classrooms`
  ```json
  // Request
  {
    "name": "Room 102",
    "capacity": 60,
    "room_type": "CLASSROOM",
    "location_description": "First Floor East Wing",
    "is_active": true,
    "facility_ids": [1, 2]
  }
  ```
* `GET /api/v1/classrooms` (Filters: `room_type`, `min_capacity`, `building_id`, `is_active`, `facility_ids`)
* `GET /api/v1/classrooms/{id}`
* `PATCH /api/v1/classrooms/{id}`
* `DELETE /api/v1/classrooms/{id}`
* `PUT /api/v1/classrooms/{id}/department-access`
  ```json
  // Request (Allowed only for room_type: LAB)
  { "department_ids": [1, 2] }
  ```
* `GET /api/v1/classrooms/{id}/department-access`

### D. Availability Query
* `GET /api/v1/availability?start_datetime=2026-10-15T09:00:00&end_datetime=2026-10-15T11:00:00&student_count=45&room_type=CLASSROOM`
  ```json
  {
    "total_eligible": 2,
    "eligible_rooms": [
      { "id": 2, "name": "Room 102", "capacity": 60, "room_type": "CLASSROOM" }
    ],
    "evaluations": [
      {
        "classroom": { "id": 1, "name": "Room 101", "capacity": 40 },
        "is_eligible": false,
        "ineligibility_reasons": ["Insufficient capacity: Room has 40 seats, needed 45."]
      }
    ]
  }
  ```

### E. Bookings & Room Unavailability
* `POST /api/v1/bookings`
  ```json
  // Request
  {
    "room_id": 1,
    "title": "Guest Lecture on Artificial Intelligence",
    "start_datetime": "2026-10-15T10:00:00Z",
    "end_datetime": "2026-10-15T12:00:00Z",
    "status": "CONFIRMED"
  }
  ```
  *(Returns `409 Conflict` if the room has an existing booking, maintenance, or published class)*
* `POST /api/v1/bookings/{id}/cancel`
* `POST /api/v1/room-unavailability`
  ```json
  // Request
  {
    "room_id": 1,
    "start_datetime": "2026-10-15T08:00:00Z",
    "end_datetime": "2026-10-15T16:00:00Z",
    "reason": "Air conditioner maintenance",
    "force": false
  }
  ```
* `GET /api/v1/room-unavailability/check-conflicts?room_id=1&start_datetime=...&end_datetime=...`

### F. Allocation & Optimization
* `POST /api/v1/allocations/generate`
  ```json
  // Request
  {
    "start_date": "2026-10-15",
    "end_date": "2026-10-15",
    "settings": {
      "time_limit_seconds": 30.0,
      "random_seed": 42,
      "num_workers": 4
    }
  }
  // Response
  {
    "id": 1,
    "status": "OPTIMAL",
    "objective_value": 46.0,
    "solver_runtime_ms": 32.5,
    "allocated_sessions": 6,
    "unallocated_sessions": 0,
    "total_sessions": 6,
    "allocations": [
      {
        "class_session_id": 1,
        "room_id": 2,
        "status": "DRAFT"
      }
    ]
  }
  ```
* `GET /api/v1/allocations/{id}/metrics` (Returns metrics and benchmark against first-fit baseline)
* `POST /api/v1/allocations/{id}/publish` (Validates and converts `DRAFT` allocations to `PUBLISHED`)
* `POST /api/v1/allocations/{id}/reoptimize` (Re-optimizes schedule with minimum disturbance to unaffected classes)

---

## 12. Troubleshooting

### Port Already in Use
If port `8000` is already in use by another application:
```bash
uvicorn app.main:app --port 8080 --reload
```

### Resetting SQLite Database
To wipe and reseed the local SQLite database cleanly:
```bash
rm -f classroom_allocation.db
alembic upgrade head
python scripts/seed_data.py
```

### ModuleNotFoundError: No module named 'app'
Ensure `PYTHONPATH` includes the `backend/` directory:
```bash
export PYTHONPATH=.
pytest
```
(Or invoke commands through the activated virtual environment inside the `backend/` directory).

