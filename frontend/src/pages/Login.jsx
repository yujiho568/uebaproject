import React, { useState } from 'react'
import { useLocation, useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const from = location.state?.from?.pathname || '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate(from, { replace: true })
    } catch (err) {
      setError('로그인 실패: 이메일 또는 비밀번호를 확인하세요')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center' }}>
      <form onSubmit={handleSubmit} style={{ width: 320, padding: 24, border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff' }}>
        <h2 style={{ marginBottom: 16 }}>로그인</h2>
        <label style={{ display: 'block', marginBottom: 8 }}>이메일</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <label style={{ display: 'block', marginBottom: 8 }}>비밀번호</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 16 }} />
        {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{ width: '100%', padding: 10, marginBottom: 12, backgroundColor: '#3b82f6', color: '#ffffff', border: 'none', borderRadius: 4 }}>
          {loading ? '로그인 중...' : '로그인'}
        </button>
        <div style={{ textAlign: 'center' }}>
          <Link to="/register">회원가입</Link>
        </div>
      </form>
    </div>
  )
}

export default Login
