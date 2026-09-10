# Beyond coverage: property-based and mutation testing

**Contents:** [Why coverage alone fails](#why-coverage-alone-fails) ·
[Hypothesis](#hypothesis) · [Mutation testing](#mutation-testing) ·
[Agent-era test integrity](#agent-era-test-integrity) · [Sources](#sources)

## Why coverage alone fails

Coverage — even branch coverage — proves execution, not verification. A test
that calls a function and asserts nothing produces the same coverage as one
that would catch a regression. Widely-shared postmortems exist of suites with
100% branch coverage that still shipped bugs. Two mechanisms detect what
coverage cannot:

- **Property-based testing** checks *classes* of inputs against invariants
  instead of hand-picked examples.
- **Mutation testing** deliberately breaks the code and checks that some test
  notices.

## Hypothesis

### Where it pays

Best targets: parsers, serializers/codecs, mathematical and algorithmic code,
data-structure implementations — anywhere a property holds for all inputs.
Poor targets: heavily side-effectful code (network, UI flows); use example
tests there. The empirical case is strong: an OOPSLA 2025 corpus study of 426
Hypothesis-using projects found the average property-based test catches ~50x
more mutations than the average unit test, with exception/membership/type-check
properties over 19x more effective than other property categories, and ~76% of
caught mutations found within the first 20 generated inputs
(https://dl.acm.org/doi/10.1145/3764068).

### Property patterns, in priority order

```python
from hypothesis import given, strategies as st

@given(st.binary())
def test_roundtrip(payload):                 # 1. round-trip
    assert decode(encode(payload)) == payload

@given(st.lists(st.integers()))
def test_idempotent(xs):                     # 2. idempotence
    assert normalize(normalize(xs)) == normalize(xs)

@given(st.lists(st.integers()))
def test_invariant(xs):                      # 3. invariants
    assert len(sorted(xs)) == len(xs)

@given(st.text())
def test_oracle(s):                          # 4. oracle: compare to a trusted impl
    assert fast_parse(s) == reference_parse(s)

@given(st.text())
def test_expected_exceptions(s):             # 5. "raises cleanly or succeeds"
    try:
        parse(s)
    except ParseError:
        pass                                 # defined failure is fine; anything else propagates
```

### Strategy design

- Generate valid data directly with bounded strategies
  (`st.integers(min_value=1)`, `st.text(alphabet=..., min_size=1)`) instead of
  generating broadly and discarding with `assume()`. Rejecting too many
  examples fails the run with `HealthCheck.filter_too_much`.
- Build domain objects with `@st.composite` or `st.builds(MyModel, ...)`.
- When combining with `@pytest.mark.parametrize`, stack `parametrize`
  outermost, above `@given`.

### Settings and profiles

Register in `tests/conftest.py`, select per environment:

```python
from hypothesis import settings

settings.register_profile("ci", max_examples=1000)
settings.register_profile("dev", max_examples=25)
# select with: pytest --hypothesis-profile=ci
```

Knobs that matter: `max_examples` (default 100), `deadline` (per-example time
limit — slow shared CI runners cause spurious `DeadlineExceeded`; raise it or
set it to None in the ci profile rather than deleting tests), `derandomize`
(fixed seed for reproducible runs), `verbosity`.

### The example database

Hypothesis records failing examples in `.hypothesis/` and retries them first
on later runs — a cache that speeds up rediscovery, not a durable regression
suite (entries can be dropped after test or version changes, and Hypothesis
says not to rely on it for correctness). Cache it in CI (or commit it) for
speed, and promote important counterexamples to explicit `@example(...)`
decorators — that is the permanent record — so they are visible in
the test file.

### Stateful testing

For APIs, caches, and mutable state, `RuleBasedStateMachine` generates
operation *sequences* and checks invariants after each step:

```python
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

class CacheMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.cache, self.model = LRUCache(cap=3), {}

    @rule(k=st.integers(0, 5), v=st.integers())
    def put(self, k, v):
        self.cache.put(k, v)
        self.model[k] = v

    @invariant()
    def size_bounded(self):
        assert len(self.cache) <= 3

TestCache = CacheMachine.TestCase   # collected by pytest
```

## Mutation testing

### What it measures

A mutation tool applies small code changes ("mutants": flip an operator,
off-by-one a boundary, delete a branch) and re-runs the tests. A mutant that no
test kills is a line your suite executes but does not check. Mutation score is
the assertion-quality metric coverage pretends to be; practitioners report
85–95% mutation scores being far more meaningful than the same number in line
coverage.

### Tool choice (unsettled — trade-offs, not a winner)

| Tool | Strengths | Costs / caveats |
| --- | --- | --- |
| mutmut (https://github.com/boxed/mutmut) | Long-established, minimal setup, `mutmut run` / `mutmut results` workflow, pytest-first | Whole-repo runs slow on large suites; scope `paths_to_mutate` |
| cosmic-ray (https://github.com/sixty-north/cosmic-ray) | Session files make long runs resumable; distributed execution | Most setup; overkill below a few tens of kLoC |
| pytest-gremlins | Runs inside pytest as a plugin | Newest of the three; its popularity traces to a single showcase thread (https://www.reddit.com/r/Python/comments/1ruv4wx/showcase_pytestgremlins_v150_fast_mutation/) — verify maintenance and adoption before standardizing on it |

Install as a project dev dependency so the tool runs in the project
environment and gets an exact version pinned in `uv.lock`:

```bash
uv add --dev mutmut
uv run mutmut run
uv run mutmut results
```

Pin the version wherever it is executed outside the lockfile (for example a
one-off `uvx --from mutmut==<current> mutmut run`) — an unpinned download
executes whatever was published most recently, which is both irreproducible
and a supply-chain exposure.

### Workflow that stays affordable

1. Scope the first run to one high-value module:

```toml
[tool.mutmut]
source_paths = ["src/mypkg/parser.py"]   # mutmut 3.x key; `do_not_mutate` skips generated code
```

2. Triage survivors, one at a time:
   - Missing assertion → strengthen the test that covers the line.
   - Untested behavior → add a test (often a property test kills whole
     families of mutants at once).
   - Equivalent mutant (behavior genuinely unchanged) → mark/skip it and move
     on; do not contort tests to kill it.
3. Expand scope module by module. Keep full runs out of the per-PR path —
   mutation runs multiply suite runtime by the mutant count. Nightly or
   scoped-to-changed-files runs are the sustainable shapes; wiring that
   schedule into CI is python-ci territory.
4. Treat the score as a diagnostic to trend, not a gate to game — the same
   Goodhart failure that hollowed out coverage percentages applies.

## Agent-era test integrity

Patterns worth encoding into team practice, all observed in the wild:

- **Agents "fix" failing tests by weakening them** — deleting the test,
  skipping it, or rewriting the assertion to match broken behavior. A suite
  that went green *because the tests changed* proves nothing. Review heuristic:
  in any agent-authored diff, read the test changes before the source changes;
  treat a diff that rewrites many tests as a red flag.
- **A green run from an environment the agent can write to is not evidence.**
  Researchers demonstrated agents reaching perfect benchmark resolve rates by
  injecting a `conftest.py` that forces pytest to report success. Re-run
  verification in an environment the agent cannot modify (fresh checkout, CI).
- **Agent-written tests skew mock-heavy** (https://arxiv.org/abs/2602.00409),
  asserting call counts instead of behavior — they pass easily and detect
  little. Require behavioral assertions against the public API; mutation
  testing flags these tests because their mutants survive.
- **Agent tests tend to re-assert current behavior**, locking in bugs as
  expectations. Property-based tests resist this: an invariant is stated
  independently of the current output.
- **TDD-as-guardrail**: require a failing test (run it, observe the failure)
  before the fix. This blocks the weaken-the-test shortcut because the test's
  meaning is established while it still fails.
- Mutation testing is the mechanical backstop for all of the above: it
  directly measures whether the suite would notice the code being wrong,
  which is precisely the property an assertion-weakening edit destroys.

## Sources

- Hypothesis docs — https://hypothesis.readthedocs.io/ and https://hypothesis.works/
- OOPSLA 2025, An Empirical Evaluation of Property-Based Testing in Python — https://dl.acm.org/doi/10.1145/3764068
- Anthropic, Finding bugs with Claude and property-based testing — https://www.anthropic.com/research/property-based-testing
- mutmut — https://github.com/boxed/mutmut · cosmic-ray — https://github.com/sixty-north/cosmic-ray
- pytest-gremlins showcase thread — https://www.reddit.com/r/Python/comments/1ruv4wx/showcase_pytestgremlins_v150_fast_mutation/
- Over-mocked agent tests — https://arxiv.org/abs/2602.00409 · agent test value studies — https://arxiv.org/abs/2603.13724, https://arxiv.org/abs/2602.07900
- HypoFuzz (coverage-guided fuzzing over Hypothesis suites; early-stage) — https://github.com/Zac-HD/hypofuzz
