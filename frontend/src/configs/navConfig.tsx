// Third-party Imports
import type * as Icon from 'lucide-react'

type IconName = keyof typeof Icon

export type MenuLeafSubItem = {
  label: string
  href: string
  activePath?: string
  badge?: string
  badgeClassName?: string
  target?: '_blank' | '_self' | '_parent' | '_top'
}

export type MenuGroupSubItem = {
  label: string
  childItems: MenuLeafSubItem[]
}

export type MenuSubItem = MenuLeafSubItem | MenuGroupSubItem

export type MenuItem = {
  icon: IconName
  label: string
} & (
  | {
      href: string
      activePath?: string
      badge?: string
      badgeClassName?: string
      childItems?: never
      target?: '_blank' | '_self' | '_parent' | '_top'
    }
  | {
      href?: never
      badge?: string
      badgeClassName?: string
      childItems: MenuSubItem[]
    }
)

export type NavItem = {
  groupLabel?: string
  items: MenuItem[]
}

/**
 * Static entries only. Run-scoped pages (Live Run, Results, Fixes, Revenue,
 * Verification, Checkout) are injected in Sidebar.tsx from the last run id
 * stored in localStorage — audit pages do not exist without a run.
 */
export const navItems: NavItem[] = [
  {
    groupLabel: 'Audit',
    items: [
      {
        icon: 'RocketIcon',
        label: 'New Audit',
        href: '/'
      }
    ]
  },
  {
    groupLabel: 'Catalog',
    items: [
      {
        icon: 'PackageIcon',
        label: 'Products',
        href: '/catalog'
      }
    ]
  }
]
