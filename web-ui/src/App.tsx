// web-ui/src/App.tsx
/**
 * MVP Web Chat Interface
 * React-based UI for nutrition research queries
 */

import React, { useState, useRef, useEffect } from 'react';
import { Send, FileText, Filter, TrendingUp } from 'lucide-react';
import './App.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: Date;
}

interface Citation {
  document_title: string;
  content: string;
  species: string;
  experiment_id?: string;
  sharepoint_url?: string;
}

interface Species {
  id: string;
  name: string;
  enabled: boolean;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [species, setSpecies] = useState<Species[]>([
    { id: 'poultry', name: 'Poultry', enabled: true },
    { id: 'swine', name: 'Swine', enabled: true },
    { id: 'aquaculture', name: 'Aquaculture', enabled: false },
  ]);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!input.trim() || loading) return;
    
    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    
    try {
      // Call RAG API
      const enabledSpecies = species
        .filter(s => s.enabled)
        .map(s => s.id);
      
      const response = await fetch('/api/v1/rag/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getAuthToken()}`
        },
        body: JSON.stringify({
          question: input,
          species: enabledSpecies,
          conversation_history: messages.slice(-6).map(m => ({
            role: m.role,
            content: m.content
          })),
          temperature: 0.3,
          max_tokens: 1500
        })
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      const data = await response.json();
      
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer,
        citations: data.citations,
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, assistantMessage]);
      
    } catch (error) {
      console.error('Error querying API:', error);
      
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your question. Please try again.',
        timestamp: new Date()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };
  
  const toggleSpecies = (speciesId: string) => {
    setSpecies(prev => prev.map(s => 
      s.id === speciesId ? { ...s, enabled: !s.enabled } : s
    ));
  };
  
  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>Nutrition Optimizer</h2>
          <p className="version">MVP v1.0</p>
        </div>
        
        <div className="species-selector">
          <h3><Filter size={16} /> Filter by Species</h3>
          {species.map(s => (
            <label key={s.id} className="species-checkbox">
              <input
                type="checkbox"
                checked={s.enabled}
                onChange={() => toggleSpecies(s.id)}
              />
              {s.name}
            </label>
          ))}
        </div>
        
        <div className="quick-actions">
          <h3>Quick Actions</h3>
          <button className="action-btn">
            <TrendingUp size={16} />
            View ETL Status
          </button>
          <button className="action-btn">
            <FileText size={16} />
            Recent Studies
          </button>
        </div>
      </div>
      
      <div className="main-content">
        <div className="chat-container">
          <div className="messages">
            {messages.length === 0 && (
              <div className="welcome-message">
                <h1>Welcome to Nutrition Optimizer</h1>
                <p>Ask questions about nutrition research across species</p>
                <div className="example-queries">
                  <button onClick={() => setInput("What are the latest vitamin D studies for poultry?")}>
                    Latest vitamin D studies for poultry
                  </button>
                  <button onClick={() => setInput("Compare bone density outcomes across species")}>
                    Compare bone density outcomes
                  </button>
                  <button onClick={() => setInput("Show me formulations with zinc oxide from 2024")}>
                    Formulations with zinc oxide from 2024
                  </button>
                </div>
              </div>
            )}
            
            {messages.map((message, index) => (
              <div key={index} className={`message ${message.role}`}>
                <div className="message-content">
                  <p>{message.content}</p>
                  
                  {message.citations && message.citations.length > 0 && (
                    <div className="citations">
                      <h4>Sources:</h4>
                      {message.citations.map((citation, i) => (
                        <div key={i} className="citation">
                          <div className="citation-header">
                            <FileText size={14} />
                            <strong>{citation.document_title}</strong>
                            <span className="species-badge">{citation.species}</span>
                          </div>
                          <p className="citation-content">{citation.content.substring(0, 200)}...</p>
                          {citation.sharepoint_url && (
                            <a href={citation.sharepoint_url} target="_blank" rel="noopener noreferrer">
                              View in SharePoint
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                <span className="timestamp">
                  {message.timestamp.toLocaleTimeString()}
                </span>
              </div>
            ))}
            
            {loading && (
              <div className="message assistant loading">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
          
          <form className="input-form" onSubmit={handleSubmit}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about nutrition research..."
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              <Send size={20} />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

function getAuthToken(): string {
  // TODO: Implement actual authentication
  // For MVP, return placeholder token
  // For production, integrate with Azure AD
  return 'mvp-token';
}

export default App;



