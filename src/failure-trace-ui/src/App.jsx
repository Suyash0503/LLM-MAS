import { useState } from "react";
import "./App.css";

const steps = [
  {
    id: 1,
    title: "Request received",
    node: "User / Frontend",
    status: "success",
    detail: "Checkout request enters the system."
  },
  {
    id: 2,
    title: "Checkout orchestrator invoked",
    node: "Checkout Orchestrator Agent",
    status: "success",
    detail: "The orchestrator starts the checkout workflow."
  },
  {
    id: 3,
    title: "Payment agent called",
    node: "Payment Agent",
    status: "success",
    detail: "Payment authorization is delegated to the Payment Agent."
  },
  {
    id: 4,
    title: "Payment service timeout",
    node: "Payment Service",
    status: "failed",
    detail: "Root cause: payment API/tool call timed out."
  },
  {
    id: 5,
    title: "Failure propagated",
    node: "Checkout Orchestrator Agent",
    status: "warning",
    detail: "Checkout cannot safely complete because payment state is unknown."
  },
  {
    id: 6,
    title: "Governance validation",
    node: "Governance Agent",
    status: "success",
    detail: "Rule validator blocks order creation and records root cause."
  }
];

const nodes = [
  { id: "user", label: "User / Frontend", x: 260, y: 40 },
  { id: "checkout", label: "Checkout Orchestrator", x: 260, y: 145 },
  { id: "paymentAgent", label: "Payment Agent", x: 260, y: 250 },
  { id: "paymentService", label: "Payment Service", x: 260, y: 355 },
  { id: "governance", label: "Governance Agent", x: 40, y: 355 },
  { id: "root", label: "Root Cause Report", x: 40, y: 250 }
];

const edges = [
  ["user", "checkout"],
  ["checkout", "paymentAgent"],
  ["paymentAgent", "paymentService"],
  ["paymentService", "governance"],
  ["governance", "root"]
];

function getNodeStatus(nodeId, currentStep) {
  if (currentStep === 0) return "idle";

  if (nodeId === "user" && currentStep >= 1) return "success";
  if (nodeId === "checkout" && currentStep >= 2 && currentStep < 5) return "success";
  if (nodeId === "paymentAgent" && currentStep >= 3) return "success";
  if (nodeId === "paymentService" && currentStep >= 4) return "failed";
  if (nodeId === "checkout" && currentStep >= 5) return "warning";
  if (nodeId === "governance" && currentStep >= 6) return "success";
  if (nodeId === "root" && currentStep >= 6) return "success";

  return "idle";
}

export default function App() {
  const [currentStep, setCurrentStep] = useState(0);
  const [running, setRunning] = useState(false);
  const [traceData, setTraceData] = useState(null);

  const runTrace = async () => {
  setCurrentStep(0);
  setRunning(true);

  try {
    const response = await fetch("http://localhost:8091/run-checkout-trace", {
  method: "POST",
});
    const data = await response.json();

    setTraceData(data);
    console.log("Runtime trace from trace-bridge:", data);

    let step = 0;
    const interval = setInterval(() => {
      step += 1;
      setCurrentStep(step);

      if (step === data.steps.length) {
        clearInterval(interval);
        setRunning(false);
      }
    }, 900);
  } catch (error) {
    console.error("Failed to fetch trace from trace-bridge:", error);
    setRunning(false);
  }
};

  return (
    <div className="page">
      <div className="background-glow" />

      <header className="header">
        <div>
          <p className="eyebrow">MAST Runtime Observability</p>
          <h1>Service-Agent Failure Trace Visualization</h1>
          <p className="subtitle">
            Interactive dependency graph showing payment failure propagation,
            root cause localization, and governance validation.
            
          </p>
        </div>

        <button className="run-button" onClick={runTrace} disabled={running}>
          {running ? "Tracing..." : "Run Payment Failure Trace"}
        </button>
      </header>

      <main className="dashboard">
        <section className="graph-card">
          <div className="card-header">
            <div>
              <h2>Runtime Dependency Graph</h2>
              <p>Nodes activate in the same order as the checkout trace.</p>
            </div>
            <span className="badge">FM: Tool Invocation Timeout</span>
          </div>

          <div className="graph-area">
            <svg className="edges">
              {edges.map(([from, to]) => {
                const fromNode = nodes.find((n) => n.id === from);
                const toNode = nodes.find((n) => n.id === to);

                return (
                  <line
                    key={`${from}-${to}`}
                    x1={fromNode.x + 90}
                    y1={fromNode.y + 72}
                    x2={toNode.x + 90}
                    y2={toNode.y}
                    className={
                      currentStep > 0 ? "edge active-edge" : "edge"
                    }
                  />
                );
              })}
            </svg>

            {nodes.map((node) => {
              const status = getNodeStatus(node.id, currentStep);

              return (
                <div
                  key={node.id}
                  className={`node ${status}`}
                  style={{ left: node.x, top: node.y }}
                >
                  <span className="node-dot" />
                  <strong>{node.label}</strong>
                  <small>
                    {status === "failed"
                      ? "ROOT CAUSE"
                      : status === "warning"
                      ? "IMPACTED"
                      : status === "success"
                      ? "ACTIVE"
                      : "WAITING"}
                  </small>
                </div>
              );
            })}
          </div>
        </section>

        <aside className="side-panel">
          <section className="timeline-card">
            <h2>Execution Trace</h2>

            <div className="timeline">
              {steps.map((step) => (
                <div
                  key={step.id}
                  className={`trace-row ${
                    currentStep >= step.id ? step.status : "idle"
                  }`}
                >
                  <span className="trace-index">{step.id}</span>
                  <div>
                    <strong>{step.title}</strong>
                    <p>{step.node}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="root-card">
            <h2>Root Cause Annotation</h2>

            {currentStep < 4 ? (
              <p className="empty-state">
                Run the trace to localize the failure origin.
              </p>
            ) : (
              <div className="analysis">
                <div>
                  <span>Root Cause</span>
                  <strong>
                   {traceData?.analysis?.root_cause || "Payment Service"}
                  </strong>
                </div>

                <div>
                  <span>Failure Type</span>
                  <strong>
                   {traceData?.analysis?.failure_type || "Tool Invocation Timeout"}
                  </strong>
                </div>

                <div>
                  <span>Propagation Path</span>
                  <strong>
                   {traceData?.analysis?.propagation_path ||
                   "Payment Service → Payment Agent → Checkout Orchestrator"}
                 </strong>
                </div>

                <div>
                 <span>System Effect</span>
               <strong>
                {traceData?.analysis?.system_effect || "Order creation blocked"}
               </strong>
              </div>

             <div>
                <span>Governance Decision</span>
              <strong>
               {traceData?.analysis?.governance_decision || "Reject unsafe checkout state"}
            </strong>
            </div>
              </div>
            )}
          </section>
        </aside>
      </main>
    </div>
  );
}