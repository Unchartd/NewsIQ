# Workflow: /release — Production Release Validation & Deployment

This workflow guides the release verification process, ensuring that the codebase is completely healthy and meets all performance, security, and migration checks prior to production deployment.

## Workflow Progression

```mermaid
graph TD
    A[QA Agent: Lint & Format Check] --> B[QA Agent: Type Check Verification]
    B --> C[QA Agent: Run Full Test Suite]
    C --> D[QA Agent: Code Coverage Audit]
    D --> E[Observability: Performance Benchmarks]
    E --> F[Security Agent: Secret & Vulnerability Scan]
    F --> G[DevOps Agent: Docker Image Build Verification]
    G --> H[Database Agent: Migration Schema Validation]
    H --> I[DevOps Agent: Trigger Production Deployment]
    I --> J[QA Agent: Execute Smoke Tests]
```

---

### Step 1: Lint & Format
- **Action**: Run lint scans (e.g. `ruff check`, `eslint`). Verify zero style errors.

### Step 2: Type Check
- **Action**: Run type checks (e.g. `mypy`, `tsc`) to guarantee type completeness.

### Step 3: Run Tests
- **Action**: Run all tests (unit, integration, pipeline). Ensure 100% success.

### Step 4: Coverage Audit
- **Action**: Verify code coverage meets project targets.

### Step 5: Performance Checks
- **Action**: Validate API response latency budgets and resource usage.

### Step 6: Security Scan
- **Action**: Run dependency audit tools and secret checkers.

### Step 7: Docker Build
- **Action**: Build Docker images locally or in CI runners to verify dependencies compile correctly.

### Step 8: Migration Validation
- **Action**: Execute and test database upgrade/downgrade migrations against a local environment.

### Step 9: Deployment
- **Action**: Tag the release branch and trigger the deployment pipeline.

### Step 10: Smoke Test
- **Action**: Run remote API checks and verify dashboard rendering on the production domain.
