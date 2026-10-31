"use client";

import { useState } from "react";

const items = [
  ["What is Verspect?", "Verspect is a self-hosted dependency intelligence tool for GitHub repositories. It inventories dependencies, analyzes available usage evidence, matches vulnerabilities, surfaces license and package-health data, and helps evaluate upgrades."],
  ["Is Verspect open source?", "Yes. The current main-branch project source is licensed under Apache-2.0. Third-party dependencies retain their own licenses, and the Verspect name, logo, and official branding are reserved."],
  ["Is Verspect a hosted service?", "No official hosted SaaS service is provided. You run the application on infrastructure you control; this public website is a separate static marketing site."],
  ["How can I install and run Verspect?", "Docker Compose is the recommended self-hosting method. Follow the repository quick-start and configure the GitHub OAuth application for your deployment."],
  ["Which ecosystems are supported?", "Python, JavaScript and TypeScript, Go, Java, Rust, PHP, and Ruby are supported with ecosystem-specific parsers and evidence."],
  ["Do all ecosystems have the same analysis capabilities?", "No. Analysis depth varies. Python has the deepest deterministic usage and migration analysis. Other ecosystems provide varying inventory, import or module usage, vulnerability, license, and health insights; advanced API and breaking-change analysis is limited."],
  ["Does Verspect require an AI provider?", "No. AI integrations are optional. Deterministic scanning and enrichment can run without a configured AI provider."],
  ["How does vulnerability detection work?", "Verspect matches package names, versions, and ecosystem information against OSV data. A missing or failed lookup does not prove that a dependency is vulnerability-free."],
  ["Can Verspect automatically create GitHub pull requests?", "A reviewed migration can be submitted after explicit confirmation. Unattended automatic pull-request creation is not enabled, and suggested changes require review and testing."],
  ["Are the landing-page demonstrations live repository scans?", "No. They use illustrative example state and do not connect to a visitor's repository or the Verspect backend."],
  ["What license applies to Verspect?", "The current main-branch project source uses Apache-2.0. The original v0.1.0-beta.1 release remains under AGPL-3.0-or-later. Third-party dependencies retain their respective licenses. Apache-2.0 does not grant rights to Verspect trademarks."],
  ["Can I contribute to Verspect?", "Yes. Read the contribution guide, review the project setup and checks, then open an issue or pull request with a focused change and relevant test results."],
] as const;

export function Faq() {
  const [active, setActive] = useState<number | null>(0);
  return <div className="faq-list">
    {items.map(([question, answer], index) => (
      <div className={`faq-item${active === index ? " active" : ""}`} key={question}>
        <h3>
          <button aria-expanded={active === index} aria-controls={`faq-answer-${index}`} onClick={() => setActive(active === index ? null : index)}>
            <span>{question}</span><span className="faq-plus" aria-hidden="true">{active === index ? "−" : "+"}</span>
          </button>
        </h3>
        <div id={`faq-answer-${index}`} className="faq-answer" hidden={active !== index}><p>{answer}</p></div>
      </div>
    ))}
  </div>;
}
