package cortex.authz

import future.keywords.if

default allow = false
default decision = "deny"
default reason = "default deny"

allow if {
	input.principal.subject != ""
	input.principal.expires_at > time.now_ns() / 1000000000
}

decision := "allow" if {
	allow
}

reason := "authenticated" if {
	allow
}
