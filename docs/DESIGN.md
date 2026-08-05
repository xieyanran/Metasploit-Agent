# Metasploit Agent Design

## Preparation

### Why Agent🧠?
- Why not using the workflow? What's the difference? What's the trde-off?

### Paradigms Chosen
Why "reinvent the wheel"?
This is my first Agent Project, which is very simple, very naive. I want to know more about the mechanism behind it, so I don't want to choose the high-abstract framwork. But this maybe will be a extention in the future.

In PTES standard(Intelligence Gathering -> Threat Modeling/Vulnerability Abalysis ->)

### Task Environment (PEAS Model)
| Dimension    | Description |
|--------------|--------------------------------------------------------|
| Performance  | Successfully exploit the target within a given time budget, measured by session establishment rate, time-to-shell, and minimal false positives/negatives in module selection. |
| Environment  | The Metasploit Framework (via RPC/msfrpc API) and the target host(s)/network, including open ports, running services, and publicly available information (e.g., CVE databases, banners). |
| Actuators    | API calls that drive the attack chain: port scan → service/version fingerprinting → matching modules → configure module (set target/payload) → set exploit options → execute exploit (retry with alternate module on failure) → establish session → post-exploitation via Meterpreter. |
| Sensors      | JSON responses from the Metasploit RPC API (scan results, module output, session status) and publicly accessible target information (banners, HTTP headers, service metadata). |

### Instruction template(system_prompt)
1. personal
2. Available Tools
3. Output format
4. Important Tips









