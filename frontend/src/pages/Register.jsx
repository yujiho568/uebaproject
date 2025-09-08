import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'

function Register() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch('/api/v1/users/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      if (!res.ok) {
        const txt = await res.text()
        throw new Error(txt || 'Registration failed')
      }
      // 성공 시 로그인 페이지로 이동
      navigate('/login', { replace: true })
    } catch (err) {
      setError('회원가입 실패: 이미 존재하는 이메일인지 확인하세요')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', alignItems: 'center', justifyContent: 'center' }}>
      <form onSubmit={handleSubmit} style={{ width: 320, padding: 24, border: '1px solid #e5e7eb', borderRadius: 8, background: '#fff' }}>
        <h2 style={{ marginBottom: 16 }}>회원가입</h2>
        <label style={{ display: 'block', marginBottom: 8 }}>이메일</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 12 }} />
        <label style={{ display: 'block', marginBottom: 8 }}>비밀번호</label>
        <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required style={{ width: '100%', padding: 8, marginBottom: 16 }} />
        {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}
        <button type="submit" disabled={loading} style={{ width: '100%', padding: 10, marginBottom: 12 }}>
          {loading ? '가입 중...' : '가입하기'}
        </button>
        <div style={{ textAlign: 'center' }}>
          <Link to="/login">로그인으로 돌아가기</Link>
        </div>
      </form>
    </div>
  )
}

export default Register
