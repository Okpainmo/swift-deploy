package swiftdeploy.infrastructure

import rego.v1

violations contains reason if {
	input.question == "pre-deploy"
	input.stats.disk_free_gb < input.limits.min_disk_free_gb
	reason := sprintf("disk free %.2fGB is below required %.2fGB", [input.stats.disk_free_gb, input.limits.min_disk_free_gb])
}

violations contains reason if {
	input.question == "pre-deploy"
	input.stats.cpu_load > input.limits.max_cpu_load
	reason := sprintf("cpu load %.2f is above allowed %.2f", [input.stats.cpu_load, input.limits.max_cpu_load])
}

deploy_decision := {
	"allowed": count(violations) == 0,
	"domain": "infrastructure",
	"question": input.question,
	"reason": reason,
	"violations": violations,
} if {
	input.question == "pre-deploy"
	reasons := [msg | some msg in violations]
	reason := concat("; ", reasons)
}

deploy_decision := {
	"allowed": false,
	"domain": "infrastructure",
	"question": input.question,
	"reason": sprintf("infrastructure policy received unsupported question %q", [input.question]),
	"violations": [sprintf("unsupported question %q", [input.question])],
} if {
	input.question != "pre-deploy"
}
