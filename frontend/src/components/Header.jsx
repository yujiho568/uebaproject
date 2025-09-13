import React from 'react'
import UserProfile from './UserProfile'

function Header({ onToggleSidebar }) {
  return (
    <header className="app-header">
      <button
        className="app-header__menu"
        aria-label="Toggle sidebar"
        onClick={onToggleSidebar}
        type="button"
      >
        <span className="app-header__menu-line"></span>
        <span className="app-header__menu-line"></span>
        <span className="app-header__menu-line"></span>
      </button>
      <div className="app-header__title">User & Entity Behavior Analytics</div>
      <UserProfile />
    </header>
  )
}

export default Header
