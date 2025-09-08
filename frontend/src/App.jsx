import React, { useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from './components/Header'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Analytics from './pages/Analytics'
import Alerts from './pages/Alerts'
import About from './pages/About'
import './App.css'

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const handleToggleSidebar = () => setSidebarOpen(prev => !prev)
  return (
    <BrowserRouter>
      <div className="app-container">
        <Header onToggleSidebar={handleToggleSidebar} />
        <div className="app-body">
          <Sidebar open={sidebarOpen} />
          <main className="app-content">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/analytics" element={<Analytics />} />
              <Route path="/alerts" element={<Alerts />} />
              <Route path="/about" element={<About />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  )
}

export default App
