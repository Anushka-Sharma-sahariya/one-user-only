import { useState } from "react";
import "@/App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [formData, setFormData] = useState({
    problem: "",
    coreUser: "",
    solution: "",
    change: "",
    metrics: "",
    outOfScope: ""
  });
  
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [apiError, setApiError] = useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // Clear error for this field when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: "" }));
    }
  };

  const validate = () => {
    const newErrors = {};
    
    // Check for empty fields
    if (!formData.problem.trim()) newErrors.problem = "Required";
    if (!formData.coreUser.trim()) newErrors.coreUser = "Required";
    if (!formData.solution.trim()) newErrors.solution = "Required";
    if (!formData.change.trim()) newErrors.change = "Required";
    if (!formData.metrics.trim()) newErrors.metrics = "Required";
    if (!formData.outOfScope.trim()) newErrors.outOfScope = "Required";
    
    // Check Core User for multiple users
    if (formData.coreUser && (
      formData.coreUser.includes(',') || 
      formData.coreUser.toLowerCase().includes(' and ') || 
      formData.coreUser.includes('/')
    )) {
      newErrors.coreUser = "Pick one user. Not a committee.";
    }
    
    // Check Success Metrics for numbers
    if (formData.metrics && !/\d/.test(formData.metrics)) {
      newErrors.metrics = "Metrics need numbers.";
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setApiError("");
    
    if (!validate()) {
      return;
    }
    
    setLoading(true);
    setResult(null);
    
    try {
      const response = await axios.post(`${API}/compress`, formData);
      setResult(response.data);
    } catch (error) {
      if (error.response?.data?.detail) {
        setApiError(error.response.data.detail);
      } else {
        setApiError("Something went wrong. Try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const renderPRD = (prdText) => {
    if (!prdText) return null;
    
    // Split by sections and render with proper formatting
    const sections = prdText.split(/\n(?=\*\*|##|###)/);
    
    return sections.map((section, idx) => {
      // Handle markdown strikethrough
      const formattedSection = section.split('~~').map((part, i) => 
        i % 2 === 1 ? <del key={i}>{part}</del> : part
      );
      
      return <div key={idx} className="prd-section">{formattedSection}</div>;
    });
  };

  return (
    <div className="App">
      {/* Hero Section */}
      <section className="hero" data-testid="hero-section">
        <h1 className="hero-title" data-testid="hero-title">Your PRD is too long.</h1>
        <p className="hero-subtitle" data-testid="hero-subtitle">
          If you can't explain it in 300 words, you don't understand it yet.
        </p>
        <button 
          className="cta-button" 
          data-testid="cta-button"
          onClick={() => document.getElementById('form-section').scrollIntoView({ behavior: 'smooth' })}
        >
          Test your thinking
        </button>
      </section>

      {/* Form Section */}
      <section className="form-section" id="form-section" data-testid="form-section">
        <form onSubmit={handleSubmit} data-testid="compress-form">
          <div className="form-group">
            <label htmlFor="problem" data-testid="problem-label">Problem</label>
            <textarea
              id="problem"
              name="problem"
              value={formData.problem}
              onChange={handleChange}
              rows="4"
              data-testid="problem-input"
            />
            {errors.problem && <span className="error-text" data-testid="problem-error">{errors.problem}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="coreUser" data-testid="core-user-label">Core User</label>
            <input
              type="text"
              id="coreUser"
              name="coreUser"
              value={formData.coreUser}
              onChange={handleChange}
              data-testid="core-user-input"
            />
            {errors.coreUser && <span className="error-text" data-testid="core-user-error">{errors.coreUser}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="solution" data-testid="solution-label">Solution</label>
            <textarea
              id="solution"
              name="solution"
              value={formData.solution}
              onChange={handleChange}
              rows="4"
              data-testid="solution-input"
            />
            {errors.solution && <span className="error-text" data-testid="solution-error">{errors.solution}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="change" data-testid="expected-change-label">Expected Change</label>
            <textarea
              id="change"
              name="change"
              value={formData.change}
              onChange={handleChange}
              rows="4"
              data-testid="expected-change-input"
            />
            {errors.change && <span className="error-text" data-testid="expected-change-error">{errors.change}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="metrics" data-testid="success-metrics-label">Success Metrics</label>
            <textarea
              id="metrics"
              name="metrics"
              value={formData.metrics}
              onChange={handleChange}
              rows="3"
              data-testid="success-metrics-input"
            />
            {errors.metrics && <span className="error-text" data-testid="success-metrics-error">{errors.metrics}</span>}
          </div>

          <div className="form-group">
            <label htmlFor="outOfScope" data-testid="out-of-scope-label">Out of Scope</label>
            <textarea
              id="outOfScope"
              name="outOfScope"
              value={formData.outOfScope}
              onChange={handleChange}
              rows="3"
              data-testid="out-of-scope-input"
            />
            {errors.outOfScope && <span className="error-text" data-testid="out-of-scope-error">{errors.outOfScope}</span>}
          </div>

          <button 
            type="submit" 
            className="submit-button" 
            disabled={loading}
            data-testid="submit-button"
          >
            {loading ? "Evaluating..." : "Evaluate My Thinking"}
          </button>
        </form>

        {/* API Error */}
        {apiError && (
          <div className="api-error" data-testid="api-error">{apiError}</div>
        )}

        {/* Result Section */}
        {result && result.status === 'rejected' && (
          <div className="rejection-message" data-testid="rejection-message">
            {result.rejection_reason}
          </div>
        )}

        {result && result.status === 'accepted' && (
          <div className="result-container" data-testid="result-container">
            {/* Maturity Level Banner */}
            <div className="maturity-banner" data-testid="maturity-banner">
              <div className="maturity-level" data-testid="maturity-level">
                {result.maturity_level}
              </div>
              <div className="overall-score" data-testid="overall-score">
                {result.overall_score?.toFixed(1)}/10
              </div>
            </div>

            {/* Diagnosis */}
            {result.diagnosis && result.diagnosis.length > 0 && (
              <div className="diagnosis-section" data-testid="diagnosis-section">
                <h3>Diagnosis</h3>
                <ul>
                  {result.diagnosis.map((item, idx) => (
                    <li key={idx} data-testid={`diagnosis-${idx}`}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Dimension Scores */}
            {result.dimension_scores && (
              <div className="dimension-scores" data-testid="dimension-scores">
                <h3>Dimension Scores</h3>
                <div className="score-grid">
                  <div className="score-item" data-testid="problem-clarity-score">
                    <span className="score-label">Problem Clarity</span>
                    <span className="score-value">{result.dimension_scores.problem_clarity?.toFixed(1)}</span>
                  </div>
                  <div className="score-item" data-testid="persona-precision-score">
                    <span className="score-label">Persona Precision</span>
                    <span className="score-value">{result.dimension_scores.persona_precision?.toFixed(1)}</span>
                  </div>
                  <div className="score-item" data-testid="solution-discipline-score">
                    <span className="score-label">Solution Discipline</span>
                    <span className="score-value">{result.dimension_scores.solution_discipline?.toFixed(1)}</span>
                  </div>
                  <div className="score-item" data-testid="metric-integrity-score">
                    <span className="score-label">Metric Integrity</span>
                    <span className="score-value">{result.dimension_scores.metric_integrity?.toFixed(1)}</span>
                  </div>
                  <div className="score-item" data-testid="scope-awareness-score">
                    <span className="score-label">Scope Awareness</span>
                    <span className="score-value">{result.dimension_scores.scope_awareness?.toFixed(1)}</span>
                  </div>
                  <div className="score-item" data-testid="ambition-level-score">
                    <span className="score-label">Ambition Level</span>
                    <span className="score-value">{result.dimension_scores.ambition_level?.toFixed(1)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Discipline Gaps */}
            {result.discipline_gaps && result.discipline_gaps.length > 0 && (
              <div className="discipline-gaps" data-testid="discipline-gaps">
                <h3>Discipline Gaps</h3>
                <ul>
                  {result.discipline_gaps.map((gap, idx) => (
                    <li key={idx} data-testid={`gap-${idx}`}>{gap}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Disciplined PRD */}
            <div className="result-card" data-testid="result-card">
              <div className="prd-header">
                <h3>Your Disciplined PRD</h3>
                <span className="word-count" data-testid="word-count">Words: {result.word_count}</span>
              </div>
              <div className="prd-content" data-testid="prd-content">
                {renderPRD(result.prd)}
              </div>
            </div>
            
            <div className="footer-message" data-testid="footer-message">
              Clarity is a skill.
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export default App;