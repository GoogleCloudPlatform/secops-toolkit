plugin "terraform" {
  enabled = true
  preset  = "recommended"
}

rule "terraform_module_pinned_source" {
  enabled = false
}

rule "terraform_required_providers" {
  enabled = false
}

rule "terraform_required_version" {
  enabled = false
}