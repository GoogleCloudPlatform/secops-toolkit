```
Title: GitHub Enterprise Disable 2FA Requirement
Description: The following analytic detects when two-factor authentication (2FA) requirements are disabled in GitHub Enterprise. The detection monitors GitHub Enterprise audit logs for 2FA requirement changes by tracking actor details, organization information, and associated metadata. For a SOC, identifying disabled 2FA requirements is critical as it could indicate attempts to weaken account security controls. Two-factor authentication is a fundamental security control that helps prevent unauthorized access even if passwords are compromised. Disabling 2FA requirements could allow attackers to more easily compromise accounts through password-based attacks. The impact of disabled 2FA includes increased risk of account takeover, potential access to sensitive code and intellectual property, and compromise of the software supply chain. This activity could be part of a larger attack chain where an adversary first disables security controls before attempting broader account compromises.
RuleId:  8302.md
Source: https://github.com/splunk/security_content/blob/develop/detections/cloud/github_enterprise_disable_2fa_requirement.yml
``` 

github_enterprise` action=org.disable_two_factor_requirement OR action=business.disable_two_factor_requirement
      | fillnull
      | stats count min(_time) as firstTime max(_time) as lastTime
        BY actor, actor_id, actor_is_bot,
           actor_location.country_code, business, business_id,
           user_agent, action
      | eval user=actor
      | `security_content_ctime(firstTime)`
      | `security_content_ctime(lastTime)`
      | `github_enterprise_disable_2fa_requirement_filter`