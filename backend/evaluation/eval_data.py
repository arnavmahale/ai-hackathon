"""Labeled test data for evaluation.

Contains:
1. RAG retrieval test queries with ground-truth relevant doc IDs
2. LLM compliance test cases with expected verdicts
3. Sample compliance documents for ingestion
"""

# ===================== Sample Compliance Documents =====================

SAMPLE_DOCUMENTS = {
    "security-guidelines": """# Security Guidelines v2.3

## Section: API Security
All API endpoints must implement JWT authentication. Every request to a protected
endpoint must include a valid JWT token in the Authorization header.

Endpoints that handle sensitive data (PII, financial records) must additionally
implement role-based access control (RBAC).

### Requirements:
- Use @require_auth decorator for all API routes
- Validate JWT token expiration
- Implement rate limiting (100 requests/minute per user)
- Log all authentication failures

## Section: Data Protection
All sensitive data must be encrypted at rest and in transit.
- Use AES-256 for encryption at rest
- Use TLS 1.2+ for data in transit
- Never log sensitive data (passwords, tokens, SSNs)
- Sanitize all user inputs to prevent injection attacks

## Section: Dependency Security
- All dependencies must be pinned to exact versions
- Run security audits monthly using pip-audit or npm audit
- No known critical CVEs allowed in production dependencies
""",

    "code-quality-standards": """# Code Quality Standards v2.3

## Section: Naming Conventions
- Function names: use camelCase (e.g., getUserData, calculateTotal)
- Class names: use PascalCase (e.g., UserManager, PaymentProcessor)
- Constants: use UPPER_SNAKE_CASE (e.g., MAX_RETRIES, API_BASE_URL)
- File names: use kebab-case (e.g., user-manager.py, api-client.js)
- Variable names: use camelCase (e.g., userName, totalCount)

## Section: Error Handling
All try/catch blocks must:
1. Log the error with full context (user ID, operation, timestamp)
2. Never use bare except/catch without specific exception types
3. Never silently swallow exceptions (no empty catch blocks)
4. Re-raise or handle appropriately — no pass in except blocks

Example of BAD error handling:
```python
try:
    risky_operation()
except:
    pass
```

Example of GOOD error handling:
```python
try:
    risky_operation()
except ValueError as e:
    logger.error("Validation failed", extra={"error": str(e), "user_id": user_id})
    raise
```

## Section: Code Quality & Structure
- Functions must not exceed 50 lines
- Maximum cyclomatic complexity: 10
- All functions must have docstrings describing purpose and parameters
- Imports must be organized: stdlib, third-party, local (separated by blank lines)

## Section: Testing Requirements
- Minimum 80% code coverage for all modules
- All public functions must have unit tests
- Integration tests required for API endpoints
- Mock external dependencies in unit tests
""",

    "documentation-requirements": """# Documentation Requirements

## Section: Code Documentation
- Every module must have a module-level docstring
- Every public function must have a docstring with:
  - Description of purpose
  - Args section with parameter types and descriptions
  - Returns section with return type and description
  - Raises section if applicable

## Section: API Documentation
- All API endpoints must be documented with OpenAPI/Swagger
- Include request/response examples
- Document error codes and their meanings
""",
}


# ===================== RAG Retrieval Test Queries =====================

RETRIEVAL_TEST_QUERIES = [
    {
        "query": "JWT authentication decorator for API endpoints",
        "relevant_doc_ids": ["security-guidelines"],
        "description": "Should retrieve security guidelines about JWT auth",
    },
    {
        "query": "try except error handling logging requirements",
        "relevant_doc_ids": ["code-quality-standards"],
        "description": "Should retrieve error handling section",
    },
    {
        "query": "function naming convention camelCase",
        "relevant_doc_ids": ["code-quality-standards"],
        "description": "Should retrieve naming conventions section",
    },
    {
        "query": "unit test coverage requirements 80%",
        "relevant_doc_ids": ["code-quality-standards"],
        "description": "Should retrieve testing requirements",
    },
    {
        "query": "docstring documentation for functions",
        "relevant_doc_ids": ["documentation-requirements", "code-quality-standards"],
        "description": "Should retrieve documentation requirements",
    },
    {
        "query": "encryption sensitive data protection AES",
        "relevant_doc_ids": ["security-guidelines"],
        "description": "Should retrieve data protection section",
    },
    {
        "query": "PascalCase class naming convention",
        "relevant_doc_ids": ["code-quality-standards"],
        "description": "Should retrieve naming conventions",
    },
    {
        "query": "rate limiting API requests per minute",
        "relevant_doc_ids": ["security-guidelines"],
        "description": "Should retrieve API security section",
    },
    {
        "query": "maximum function length lines of code",
        "relevant_doc_ids": ["code-quality-standards"],
        "description": "Should retrieve code structure requirements",
    },
    {
        "query": "dependency pinning security audit CVE",
        "relevant_doc_ids": ["security-guidelines"],
        "description": "Should retrieve dependency security section",
    },
]


# ===================== LLM Compliance Test Cases =====================

COMPLIANCE_TEST_CASES = [
    # --- Should detect violations ---
    {
        "code": """
@app.route('/api/users')
def get_users():
    return jsonify(users)
""",
        "file_path": "api/routes.py",
        "task": {
            "id": "task_001",
            "title": "Enforce JWT validation for API endpoints",
            "description": "Every API endpoint must verify JWT authentication before processing requests.",
            "severity": "critical",
            "checkType": "Security Pattern Detection",
        },
        "expected_compliant": False,
        "reason": "No auth decorator on API endpoint",
    },
    {
        "code": """
try:
    result = database.query(sql)
except:
    pass
""",
        "file_path": "services/db_service.py",
        "task": {
            "id": "task_002",
            "title": "Ensure all try/catch blocks log errors",
            "description": "All try/catch blocks must log errors with context. Empty catch blocks are not allowed.",
            "severity": "critical",
            "checkType": "Error Handling Pattern",
        },
        "expected_compliant": False,
        "reason": "Bare except with pass — swallows exception",
    },
    {
        "code": """
def get_user_data():
    pass

def calculate_total_price():
    pass

def fetch_all_records():
    pass
""",
        "file_path": "utils/helpers.py",
        "task": {
            "id": "task_005",
            "title": "Enforce camelCase for function names",
            "description": "All function names must use camelCase.",
            "severity": "warning",
            "checkType": "Naming Convention Pattern",
        },
        "expected_compliant": False,
        "reason": "Functions use snake_case instead of camelCase",
    },
    {
        "code": """
class user_manager:
    def __init__(self):
        self.users = []

class payment_processor:
    pass
""",
        "file_path": "models/entities.py",
        "task": {
            "id": "task_006",
            "title": "Enforce PascalCase for class names",
            "description": "All class names must use PascalCase.",
            "severity": "warning",
            "checkType": "Naming Convention Pattern",
        },
        "expected_compliant": False,
        "reason": "Classes use snake_case instead of PascalCase",
    },
    {
        "code": """
def process_data():
    x = get_input()
    y = transform(x)
    z = validate(y)
    return z

def helper():
    return 42
""",
        "file_path": "core/processor.py",
        "task": {
            "id": "task_009",
            "title": "Ensure all functions have docstrings",
            "description": "Every function must have a docstring.",
            "severity": "info",
            "checkType": "Docstring Check",
        },
        "expected_compliant": False,
        "reason": "Functions have no docstrings",
    },
    # --- Should be compliant ---
    {
        "code": """
@app.route('/api/users')
@require_auth
def get_users():
    return jsonify(users)
""",
        "file_path": "api/routes.py",
        "task": {
            "id": "task_001",
            "title": "Enforce JWT validation for API endpoints",
            "description": "Every API endpoint must verify JWT authentication before processing requests.",
            "severity": "critical",
            "checkType": "Security Pattern Detection",
        },
        "expected_compliant": True,
        "reason": "Has @require_auth decorator",
    },
    {
        "code": """
try:
    result = database.query(sql)
except DatabaseError as e:
    logger.error("Query failed", extra={"error": str(e), "query": sql})
    raise
""",
        "file_path": "services/db_service.py",
        "task": {
            "id": "task_002",
            "title": "Ensure all try/catch blocks log errors",
            "description": "All try/catch blocks must log errors with context. Empty catch blocks are not allowed.",
            "severity": "critical",
            "checkType": "Error Handling Pattern",
        },
        "expected_compliant": True,
        "reason": "Specific exception type, logs error with context, re-raises",
    },
    {
        "code": """
def getUserData():
    pass

def calculateTotalPrice():
    pass

def fetchAllRecords():
    pass
""",
        "file_path": "utils/helpers.py",
        "task": {
            "id": "task_005",
            "title": "Enforce camelCase for function names",
            "description": "All function names must use camelCase.",
            "severity": "warning",
            "checkType": "Naming Convention Pattern",
        },
        "expected_compliant": True,
        "reason": "All functions use camelCase",
    },
    {
        "code": """
class UserManager:
    def __init__(self):
        self.users = []

class PaymentProcessor:
    pass
""",
        "file_path": "models/entities.py",
        "task": {
            "id": "task_006",
            "title": "Enforce PascalCase for class names",
            "description": "All class names must use PascalCase.",
            "severity": "warning",
            "checkType": "Naming Convention Pattern",
        },
        "expected_compliant": True,
        "reason": "All classes use PascalCase",
    },
    {
        "code": """
def process_data():
    \"\"\"Process incoming data through the transformation pipeline.\"\"\"
    x = get_input()
    y = transform(x)
    return y

def helper():
    \"\"\"Return a constant value for testing.\"\"\"
    return 42
""",
        "file_path": "core/processor.py",
        "task": {
            "id": "task_009",
            "title": "Ensure all functions have docstrings",
            "description": "Every function must have a docstring.",
            "severity": "info",
            "checkType": "Docstring Check",
        },
        "expected_compliant": True,
        "reason": "All functions have docstrings",
    },
]
