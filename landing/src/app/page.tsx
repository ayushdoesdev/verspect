import Link from "next/link";
import { Faq } from "@/components/faq";
import { SiteFooter } from "@/components/site-footer";
import { SiteNav } from "@/components/site-nav";

const repository = "https://github.com/ayushdoesdev/verspect";
const install = `${repository}#quick-start-with-docker-compose`;

const capabilities = [
  { icon: "↗", name: "Dependency intelligence", text: "Explore direct and transitive dependencies, package inventory, and relationships revealed by supported manifests and lockfiles." },
  { icon: "⌁", name: "Security analysis", text: "Match package versions with OSV advisories and review severity and affected-version evidence where available." },
  { icon: "§", name: "License analysis", text: "Inspect package license information and policy concerns, with gaps shown when source or registry metadata is incomplete." },
  { icon: "◷", name: "Package health", text: "Review signals such as release freshness and registry activity when the underlying metadata is available." },
  { icon: "⇄", name: "Upgrade simulator", text: "Compare current and target versions against detected usage and available upgrade rules. Findings depend on the evidence present." },
  { icon: "⌘", name: "Migration assistant", text: "Use structured rules and optional AI-assisted suggestions or patch drafts. Review and test every proposed change." },
];

const ecosystems = ["Python", "JavaScript / TypeScript", "Go", "Java", "Rust", "PHP", "Ruby"];

export default function Home() {
  return <>
    <Link className="skip-link" href="#main">Skip to content</Link>
    <SiteNav />
    <main id="main">
      <section className="hero section-grid" id="top">
        <div className="hero-glow" />
        <div className="container hero-content">
          <div className="hero-copy">
            <div className="eyebrow"><span className="status-dot" /> Open-source dependency intelligence</div>
            <h1>Know your dependencies.<br /><span>Understand your risks.</span><br />Upgrade with confidence.</h1>
            <p className="hero-lede">Dependency intelligence for GitHub repositories. Discover what your software depends on, understand security and license risks, explore package health, and evaluate upgrade impact with evidence-led analysis and AI-assisted migration guidance.</p>
            <div className="hero-actions">
              <a className="button button-primary" href={repository} target="_blank" rel="noreferrer noopener">View on GitHub <span aria-hidden="true">↗</span></a>
              <a className="button button-secondary" href={install} target="_blank" rel="noreferrer noopener">Get Started <span aria-hidden="true">→</span></a>
            </div>
            <ul className="product-attributes" aria-label="Product attributes">
              <li><span>◈</span> Open Source</li><li><span>◈</span> Apache-2.0</li><li><span>◈</span> Self-hosted</li><li><span>◈</span> Docker Compose</li>
            </ul>
          </div>
          <HeroPreview />
          <p className="illustrative-note"><span aria-hidden="true">ⓘ</span> Illustrative product preview · example repository data, not a live scan</p>
        </div>
      </section>

      <section className="section" id="features">
        <div className="container">
          <SectionHeading eyebrow="Product overview" title="Understand your dependencies beyond the version number." description="Follow packages from the manifest into usage, risk, and upgrade evidence so decisions have context." />
          <div className="capability-grid">
            {capabilities.map((item, i) => <article className="capability-card" key={item.name}>
              <div className="capability-icon" aria-hidden="true">{item.icon}</div><span className="card-index">0{i + 1}</span>
              <h3>{item.name}</h3><p>{item.text}</p>
            </article>)}
          </div>
        </div>
      </section>

      <section className="section section-muted" id="scanning">
        <div className="container split-layout">
          <div><SectionHeading eyebrow="Repository scanning" title="From repository to useful evidence." description="A scan follows a visible path through repository discovery, dependency indexing, usage analysis, and metadata enrichment." />
            <ul className="check-list"><li>Find supported manifests and lockfiles</li><li>Build inventory and dependency relationships</li><li>Map imports and usage evidence by ecosystem</li><li>Enrich with vulnerability, license, and health data</li></ul>
          </div>
          <ScanPreview />
        </div>
      </section>

      <section className="section" id="simulator">
        <div className="container split-layout reverse-on-wide">
          <UpgradePreview />
          <div><SectionHeading eyebrow="Upgrade simulator" title="See the context around an upgrade." description="Compare a current version with a target and review the usage and migration evidence available for that change." />
            <p className="body-copy">A version jump is not automatically labeled breaking. The simulator reports what its rules and repository evidence support, and leaves uncertainty visible.</p>
            <span className="demo-tag">Illustrative example · no live compatibility claim</span>
          </div>
        </div>
      </section>

      <section className="section section-muted" id="migration">
        <div className="container split-layout">
          <div><SectionHeading eyebrow="Migration assistant" title="Turn migration context into a reviewable draft." description="Bring together structured migration knowledge, detected usage, and optional AI assistance." />
            <p className="body-copy">Deterministic migration knowledge is currently deepest for selected Python packages. AI-generated guidance and patch drafts are suggestions: review, run, and test them before adoption.</p>
          </div><MigrationPreview />
        </div>
      </section>

      <section className="section" id="insights">
        <div className="container">
          <SectionHeading eyebrow="Connected insights" title="Follow package relationships. Put findings in context." description="Explore how dependencies connect and where security evidence appears in the tree." />
          <div className="insights-grid"><GraphPreview /><SecurityPreview /></div>
        </div>
      </section>

      <section className="section section-muted" id="ecosystems">
        <div className="container ecosystem-layout">
          <div><SectionHeading eyebrow="Ecosystem support" title="Built for multiple dependency ecosystems." description="Verspect reads ecosystem-specific manifests, lockfiles, and source files; analysis depth differs by language." />
            <p className="body-copy">Python has the deepest deterministic usage and migration analysis. Other ecosystems provide varying levels of inventory, import or module usage, vulnerability, license, and health analysis. Full API-level and language-specific breaking-change analysis remains limited.</p>
            <a className="text-link" href={`${repository}/blob/main/docs/languages.md`} target="_blank" rel="noreferrer noopener">Read the language support details <span aria-hidden="true">↗</span></a>
          </div>
          <div className="ecosystem-card"><div className="ecosystem-card-head"><span>SUPPORTED INPUTS</span><span className="mono">01 — 07</span></div><ul>{ecosystems.map((name, index) => <li key={name}><span className="ecosystem-number">0{index + 1}</span><span>{name}</span><span className="ecosystem-arrow">↗</span></li>)}</ul><p>Capabilities vary by ecosystem and available repository evidence.</p></div>
        </div>
      </section>

      <section className="section" id="workflow">
        <div className="container"><SectionHeading eyebrow="How it works" title="Your repository stays in your workflow." description="Repository analysis happens in the self-hosted Verspect application, not on this public website." />
          <div className="workflow-grid">{[
            ["01", "Self-host", "Run Verspect on infrastructure you control with Docker Compose."],
            ["02", "Connect GitHub", "Configure OAuth, then choose a repository to import."],
            ["03", "Review evidence", "Scan dependencies and inspect inventory, usage, and findings."],
            ["04", "Plan an upgrade", "Evaluate impact and review migration recommendations."],
          ].map(([num, title, text]) => <article className="workflow-card" key={num}><span className="workflow-num">{num}</span><div className="workflow-connector" aria-hidden="true" /><h3>{title}</h3><p>{text}</p></article>)}</div>
        </div>
      </section>

      <section className="section hosting-section" id="self-hosting">
        <div className="container"><div className="hosting-panel">
          <div className="hosting-orbit" aria-hidden="true" />
          <div className="hosting-copy"><div className="eyebrow"><span className="status-dot" /> Self-hosted open source</div><h2>Your infrastructure.<br /><span>Your control.</span></h2><p>Verspect runs on infrastructure you manage. Docker Compose is the recommended setup, AI integrations are optional, and the complete source is available for inspection.</p>
            <div className="hosting-actions"><a className="button button-primary" href={repository} target="_blank" rel="noreferrer noopener">Explore the GitHub Repository <span>↗</span></a><a className="button button-secondary" href={install}>Read Installation Guide <span>→</span></a></div>
          </div>
          <div className="hosting-facts"><Fact label="Deployment" value="Self-hosted" /><Fact label="Recommended setup" value="Docker Compose" /><Fact label="Current main source" value="Apache-2.0" /><Fact label="AI provider" value="Optional" /></div>
        </div>
          <div className="license-note"><span className="license-mark">§</span><p>The current main-branch source uses Apache-2.0. The original <code>v0.1.0-beta.1</code> release remains under AGPL-3.0-or-later. Third-party dependencies keep their respective licenses. Verspect name, logo, and official branding are reserved; Apache-2.0 does not grant trademark rights.</p><div><a href={`${repository}/blob/main/LICENSE`} target="_blank" rel="noreferrer noopener">License ↗</a><a href={`${repository}/blob/main/THIRD_PARTY_NOTICES.md`} target="_blank" rel="noreferrer noopener">Third-party notices ↗</a></div></div>
        </div>
      </section>

      <section className="section section-muted" id="project-activity">
        <div className="container activity-row"><div><div className="eyebrow">Project activity</div><h2>Follow the project as it develops.</h2><p>Explore releases, report an issue, contribute a change, or review the security policy.</p></div><div className="activity-links">
          <ActivityLink href={`${repository}/releases`} label="Releases" detail="Version history" /><ActivityLink href={`${repository}/issues`} label="Issues" detail="Discuss a problem" /><ActivityLink href={`${repository}/blob/main/CONTRIBUTING.md`} label="Contributions" detail="How to take part" /><ActivityLink href={`${repository}/blob/main/SECURITY.md`} label="Security policy" detail="Private reporting" />
        </div></div>
      </section>

      <section className="section" id="faq">
        <div className="container faq-layout"><SectionHeading eyebrow="FAQ" title="Common questions, clearly answered." description="A quick guide to what Verspect does today and how this site relates to the application." /><Faq /></div>
      </section>

      <section className="final-cta" id="documentation">
        <div className="container final-cta-inner"><div className="cta-glow" /><div className="eyebrow">Explore the source</div><h2>Explore the source.<br /><span>Understand your dependencies.</span></h2><p>Explore Verspect, inspect its implementation, and run it on your own infrastructure.</p><div className="hero-actions"><a className="button button-primary" href={repository} target="_blank" rel="noreferrer noopener">View Verspect on GitHub <span>↗</span></a><a className="button button-secondary" href={`${repository}#readme`} target="_blank" rel="noreferrer noopener">Read the Documentation <span>↗</span></a></div></div>
      </section>
    </main>
    <SiteFooter />
  </>;
}

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="section-heading"><div className="eyebrow">{eyebrow}</div><h2>{title}</h2><p>{description}</p></div>;
}

function HeroPreview() {
  return <div className="hero-preview">
    <div className="preview-shadow" />
    <div className="terminal-window window">
      <WindowTitle title="verspect · scan summary · example/service-api" tag="EXAMPLE" />
      <div className="terminal-body"><div className="terminal-sidebar"><span className="side-label">WORKSPACE</span><span className="side-active">◉ &nbsp; service-api</span><span>⌕ &nbsp; Dependencies</span><span>◇ &nbsp; Security</span><span>▦ &nbsp; Upgrades</span><div className="side-user"><span className="user-dot">v</span><span>local workspace</span></div></div>
        <div className="terminal-main"><div className="terminal-command"><span className="terminal-prompt">$</span> verspect scan service-api</div><div className="terminal-divider" />
          {["Repository import complete", "Manifest and lockfile discovery", "Dependency indexing", "Usage evidence collected", "OSV, license & health enrichment"].map((line, i) => <div className="terminal-step" key={line}><span className="step-check">{i < 5 ? "✓" : "·"}</span><span>{line}</span><span className="step-state">{["READY", "12 FILES", "186 PKGS", "94 FILES", "READY"][i]}</span></div>)}
          <div className="scan-progress"><span>EXAMPLE WORKFLOW</span><span>COMPLETE</span><i /></div>
        </div>
      </div>
    </div>
    <div className="metrics-window window"><WindowTitle title="repository overview" /><div className="metrics-content"><div className="metric-top"><div><span className="metric-label">DEPENDENCY INVENTORY</span><strong>186</strong></div><span className="metric-pill">example state</span></div><div className="metric-cards"><Metric label="Direct" value="42" /><Metric label="Transitive" value="144" /><Metric label="OSV matches" value="3" /></div><div className="metric-bars"><Bar label="Inventory" value="100%" width="100%" /><Bar label="Evidence coverage" value="76%" width="76%" /><Bar label="Metadata available" value="83%" width="83%" /></div></div></div>
  </div>;
}

function ScanPreview() {
  const lines = [["01", "Repository imported", "done"], ["02", "Manifests & lockfiles found", "6 files"], ["03", "Dependency inventory built", "186 packages"], ["04", "Usage evidence indexed", "94 files"], ["05", "OSV and registry enrichment", "example"]];
  return <div className="window scan-window"><WindowTitle title="scan workflow · illustrative" tag="EXAMPLE" /><div className="scan-timeline">{lines.map(([num, text, status]) => <div className="scan-line" key={num}><span>{num}</span><b>{text}</b><em>{status}</em></div>)}</div><div className="scan-footer"><span className="status-dot" /> Example scan flow · no live connection</div></div>;
}

function UpgradePreview() {
  return <div className="window upgrade-window"><WindowTitle title="upgrade simulator · illustrative" tag="EXAMPLE" /><div className="upgrade-body"><div className="package-select"><span>PACKAGE</span><b>fastapi <i>⌄</i></b></div><div className="version-compare"><div><span>CURRENT VERSION</span><strong>0.110.0</strong></div><span className="compare-arrow">→</span><div><span>TARGET VERSION</span><strong>0.115.0</strong></div></div><div className="evidence-box"><div><span className="evidence-icon">✓</span><b>Usage evidence</b><small>Imports found in 8 files</small></div><div><span className="evidence-icon muted-icon">◌</span><b>Migration rules</b><small>Review available package notes</small></div></div><div className="risk-note"><span>i</span><p>Example only. Compatibility and impact depend on repository evidence and available rules.</p></div></div></div>;
}

function MigrationPreview() {
  return <div className="window migration-window"><WindowTitle title="migration assistant · draft" tag="REVIEW REQUIRED" /><div className="migration-content"><div className="migration-context"><span>PYTHON · SELECTED PACKAGE RULE</span><b>Example configuration migration</b><small>Evidence: configuration usage found · rule availability varies</small></div><div className="code-diff"><div><span>−</span><code>from package import LegacyClient</code></div><div className="diff-add"><span>+</span><code>from package import Client</code></div><div><span> </span><code>client = Client(timeout=30)</code></div></div><div className="migration-explain"><span className="ai-spark">✳</span><p><b>Suggested draft</b><br />Review API compatibility and validate this change against the target release.</p></div><div className="migration-foot"><span>Human review required</span><span>Save patch draft&nbsp; →</span></div></div></div>;
}

function GraphPreview() {
  return <article className="window insight-window"><WindowTitle title="dependency relationships" /><div className="graph-canvas"><svg viewBox="0 0 560 260" role="img" aria-label="Illustrative package relationship graph"><g className="graph-edges"><path d="M280 62 130 140M280 62 430 140M130 140 76 218M130 140 226 218M430 140 360 218M430 140 490 218" /><path d="M280 62 280 218" /></g><GraphNode x={280} y={56} label="service-api" kind="root" /><GraphNode x={130} y={135} label="fastapi" /><GraphNode x={430} y={135} label="httpx" /><GraphNode x={76} y={220} label="starlette" kind="risk" /><GraphNode x={226} y={220} label="pydantic" /><GraphNode x={360} y={220} label="anyio" /><GraphNode x={490} y={220} label="certifi" /></svg><div className="graph-legend"><span><i className="legend-root" /> repository</span><span><i /> dependency</span><span><i className="legend-risk" /> finding example</span></div></div><p className="card-caption">Illustrative graph · relationships depend on available manifests and lockfiles.</p></article>;
}

function GraphNode({ x, y, label, kind = "normal" }: { x: number; y: number; label: string; kind?: string }) {
  return <g className={`graph-node ${kind}`}><rect x={x - 46} y={y - 16} width="92" height="32" rx="9" /><text x={x} y={y + 4} textAnchor="middle">{label}</text></g>;
}

function SecurityPreview() {
  return <article className="window security-window"><WindowTitle title="security findings · example data" tag="OSV" /><div className="security-body"><div className="security-summary"><div><span>PACKAGE</span><b>example-lib</b></div><div><span>INSTALLED</span><b>1.2.0</b></div><div><span>SEVERITY</span><b className="severity">High</b></div></div><div className="finding-card"><div><span className="finding-dot" /><b>Advisory match</b><span className="finding-id">OSV · illustrative</span></div><p>Version range and ecosystem are checked against vulnerability data.</p><div className="range-row"><span>Installed version</span><code>1.2.0</code><span className="range-line" /><span>Fixed version</span><code>check source</code></div></div><div className="security-foot">A lookup result is evidence, not a guarantee of a clean dependency.</div></div></article>;
}

function WindowTitle({ title, tag }: { title: string; tag?: string }) {
  return <div className="window-title"><div className="window-dots"><i /><i /><i /></div><span>{title}</span>{tag && <b>{tag}</b>}</div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div className="metric-card"><span>{label}</span><b>{value}</b></div>; }
function Bar({ label, value, width }: { label: string; value: string; width: string }) { return <div className="bar-row"><span>{label}</span><b>{value}</b><i><em style={{ width }} /></i></div>; }
function Fact({ label, value }: { label: string; value: string }) { return <div className="hosting-fact"><span>{label}</span><b>{value}</b></div>; }
function ActivityLink({ href, label, detail }: { href: string; label: string; detail: string }) { return <a className="activity-link" href={href} target="_blank" rel="noreferrer noopener"><span><b>{label}</b><small>{detail}</small></span><i aria-hidden="true">↗</i></a>; }
