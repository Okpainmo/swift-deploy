package swiftdeploy.canary

import rego.v1

violations contains reason if {
	input.question == "pre-promote"
	input.metrics.error_rate > input.limits.max_error_rate
	reason := sprintf("error rate %.2f%% is above allowed %.2f%%", [input.metrics.error_rate * 100, input.limits.max_error_rate * 100])
}

violations contains reason if {
	input.question == "pre-promote"
	input.metrics.p99_latency_ms > input.limits.max_p99_latency_ms
	reason := sprintf("p99 latency %.2fms is above allowed %.2fms", [input.metrics.p99_latency_ms, input.limits.max_p99_latency_ms])
}

promotion_decision := {
	"allowed": count(violations) == 0,
	"domain": "canary",
	"question": input.question,
	"reason": reason,
	"violations": violations,
} if {
	input.question == "pre-promote"
	reasons := [msg | some msg in violations]
	reason := concat("; ", reasons)
}

promotion_decision := {
	"allowed": false,
	"domain": "canary",
	"question": input.question,
	"reason": sprintf("canary policy received unsupported question %q", [input.question]),
	"violations": [sprintf("unsupported question %q", [input.question])],
} if {
	input.question != "pre-promote"
}
