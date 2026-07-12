# Simulation, measurement, and outcome contract

> Status: APPROVED  
> Date: 2026-07-11

## 1. Purpose

This contract makes synthetic development time, measurements, and outcomes deterministic and testable. It prevents wall-clock behavior, ambiguous units, and LLM-generated outcomes from becoming system truth.

## 2. Simulation clock

The Outcome Engine uses a logical integer clock.

```yaml
simulation_clock:
  case_id: CASE-VR-001
  current_step: 12
  current_milestone_id: M2_ARCH_FREEZE
```

Rules:

- `simulation_step` starts at 0.
- Time advances only through an explicit `advance-outcome` command.
- API/DB wall-clock timestamps are audit metadata, not simulation state.
- Replaying the same frozen case, decision, and step count produces the same outcome.

## 3. Time fields

|Field|Meaning|
|---|---|
|`planned_at_step`|planned start/completion|
|`effective_at_step`|when a development fact becomes true|
|`observed_at_step`|when the simulated organization learns the fact|
|`available_at_step`|when evidence becomes accessible to agents|
|`expires_at_step`|when an assumption/waiver must be reviewed|
|`recorded_at`|real audit timestamp|

Agents receive facts only when `available_at_step <= current_step`.

## 4. Quantity contract

```yaml
quantity:
  mode: exact  # exact | range | qualitative | unknown
  value: 1850.0
  lower_bound: null
  upper_bound: null
  qualitative: null
  unit: mW
```

Validation:

- `exact` requires `value` only.
- `range` requires lower and upper bounds.
- `qualitative` requires one of `low`, `medium`, `high`, `critical`.
- `unknown` carries no numeric value.
- Numeric comparisons require the same dimension and canonical unit.

## 5. Canonical units

|Dimension|Canonical unit|Display examples|
|---|---|---|
|Power|`mW`|850 mW, 1850 mW|
|Energy|`mJ`|120 mJ|
|Memory bandwidth|`GB/s`|18.5 GB/s|
|Bit rate|`Mbps`|120 Mbps|
|Latency|`ms`|42 ms|
|Frame rate|`fps`|60 fps|
|Temperature|`degC`|78 °C|
|Area|`mm2`|1.25 mm²|
|Utilization/ratio|`ratio` in 0..1|UI displays 85%|
|Count|`count`|3 underruns|
|Development effort|`person_day`|12 person-days|
|Simulation duration|`step`|5 steps|

Do not use `Gbps` for memory byte bandwidth or mix percentage 85 with ratio 0.85 internally.

## 6. Measurement contract

```yaml
measurement:
  id: MEAS-BW-001
  target_id: SCN-UHD60-EIS-ON
  metric_id: DDR_BANDWIDTH
  quantity:
    mode: range
    lower_bound: 17.0
    upper_bound: 20.0
    unit: GB/s
  evidence_type: model_prediction
  effective_at_step: 8
  observed_at_step: 9
  available_at_step: 9
  source_ref: FIXTURE:MODEL-BW-001
  confidence: medium
  limitations:
    - not_silicon_measurement
```

Evidence types:

```text
assumption
analytical_estimate
simulation_prediction
emulation_measurement
silicon_measurement
customer_observation
expert_review
```

Evidence type does not automatically determine confidence; source match, freshness, method, and limitation also apply.

## 7. Development event contract

```yaml
development_event:
  id: EVT-001
  case_id: CASE-VR-001
  event_type: work_completed
  effective_at_step: 13
  target_ids: [WORK-SW-FLAG]
  preconditions: []
  state_changes: []
  reveals_evidence_ids: []
  source: outcome_rule
```

Event ordering is by `(effective_at_step, priority, event_id)`.

## 8. Outcome rule implementation

MVP rules are typed Python classes registered by stable rule ID.

```python
class OutcomeRule(Protocol):
    rule_id: str

    def validate(self, case, parameters) -> list[Violation]: ...
    def apply(
        self,
        context: OutcomeContext,
        state: SimulationState,
        decision: SimulatedDecision,
        parameters: RuleParameters,
    ) -> OutcomeDelta: ...
```

`OutcomeContext` contains `case_id`, `fixture_version`, `decision_id`, `from_step`, `to_step`, `outcome_rule_version`, and prior event IDs. Generated event IDs derive deterministically from this input.

Fixture files may reference a rule and parameters but may not contain executable expressions.

```yaml
outcome_rule:
  rule_id: guarded_sw_eis_path.v1
  parameters:
    bw_trigger_gb_s: 20.0
    thermal_trigger_deg_c: 82.0
    reveal_measurement_at_step: 15
```

## 9. Closed-world option policy

- Decision Chair may select only option IDs in the Observable Case Packet.
- The selected option set must match a defined outcome path or a registered composition rule.
- Unknown options or combinations fail with `OUTCOME_PATH_UNDEFINED`.
- LLM output never creates a new hidden path.
- Adding an option requires fixture, rule validation, and expected evaluation updates.

## 10. Rule priority and conflict

1. safety constraint
2. hard development precondition
3. selected option outcome
4. guardrail/trigger
5. general progression

Two rules that produce incompatible changes at the same priority fail the run with `OUTCOME_RULE_CONFLICT`. The engine must not choose arbitrarily.

## 11. Guardrail and trigger execution

```yaml
guardrail:
  id: GR-BW-LIMIT
  metric_id: DDR_BANDWIDTH
  operator: lte
  threshold:
    mode: exact
    value: 20.0
    unit: GB/s
  check_at_steps: [15, 16, 17]
  violation_action: rollback
  action_owner: ROLE-SW-OWNER
```

Every executable trigger requires:

- observable metric
- canonical unit
- comparison operator
- threshold
- check step or milestone
- violation action
- action owner

## 12. Idempotency

`advance-outcome(case_id, decision_id, from_step, to_step)` is idempotent. Repeating the same command returns the prior result. Advancing from an outdated step fails with `SIMULATION_STEP_CONFLICT`.

## 13. Hidden access

Only these application ports may read hidden state:

- `OutcomeRepository`
- `EvaluationRepository`

Role, Challenger, Chair, workspace projection, and user API modules cannot depend on these ports.

## 14. Required tests

- same input produces same event sequence
- future evidence is absent before available step
- wall-clock changes do not change outcome
- incompatible units fail
- exact/range/qualitative validation
- unknown option fails closed
- rule conflict fails rather than selecting one
- guardrail violation triggers configured action
- repeated advance is idempotent
- outdated step is rejected
- hidden repository is unreachable from Agent/Chair dependency graph
