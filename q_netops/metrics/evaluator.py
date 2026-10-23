"""Summarize controller outcomes with clearly defined denominators."""
import pandas as pd

def summarize(results: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(results)
    summary = frame.groupby("policy", as_index=False).agg(
        success_rate=("delivered", "mean"),
        mean_fidelity=("fidelity", "mean"),
        mean_latency_s=("latency_s", "mean"),
        mean_memory_utilization=("memory_utilization", "mean"),
        mean_generation_attempts=("generation_attempts", "mean"),
        mean_wasted_attempts=("wasted_attempts", "mean"),
    )
    if "actual_failure" in frame:
        frame["fidelity_qualified"] = frame.delivered & (frame.fidelity >= frame.target_fidelity)
        frame["expired"] = frame.action.eq("RETRACT")
        extra = frame.groupby("policy", as_index=False).agg(
            fidelity_constraint_rate=("fidelity_qualified", "mean"),
            request_expiration_rate=("expired", "mean"),
        )
        summary = summary.merge(extra, on="policy", how="left")
    if "predicted_failure_risk" in frame:
        risk_rows = frame[frame.predicted_failure_risk.notna()].copy()
        if not risk_rows.empty:
            risk_rows["risk_calibration_gap"] = (
                risk_rows.predicted_failure_risk - risk_rows.actual_failure.astype(float)
            )
            risk_summary = risk_rows.groupby("policy", as_index=False).agg(
                mean_modeled_failure_risk=("predicted_failure_risk", "mean"),
                mean_risk_calibration_gap=("risk_calibration_gap", "mean"),
            )
            summary = summary.merge(risk_summary, on="policy", how="left")
    if "local_repairs" in frame:
        repaired = frame[frame.local_repairs > 0]
        recovery = repaired.groupby("policy", as_index=False).agg(
            recovery_success_rate=("delivered", "mean"),
            mean_repairs_per_repaired_request=("local_repairs", "mean"),
        )
        summary = summary.merge(recovery, on="policy", how="left")
    delivered_fidelity = (frame[frame.delivered].groupby("policy").fidelity.mean()
                          .rename("mean_delivered_fidelity"))
    return summary.merge(delivered_fidelity, on="policy", how="left")
