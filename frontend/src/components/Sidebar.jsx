import React from 'react'
import { NavLink } from 'react-router-dom'

const navItems = [
  { path: '/', label: 'Dashboard' },
  { path: '/results', label: 'Results' },
  { path: '/connect', label: 'Connect' },
  { path: '/guide', label: 'Guide' },
]

function Sidebar({ open }) {
  return (
    <aside className={`app-sidebar${open ? ' app-sidebar--open' : ''}`}>
      <nav className="app-nav">
        {navItems.map(item => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `app-nav__link${isActive ? ' app-nav__link--active' : ''}`
            }
            end={item.path === '/'}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

export default Sidebar
