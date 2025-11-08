import type { JSX } from 'react';
import { Shield, Upload, ClipboardList, GitBranch } from 'lucide-react';
import type { PageKey } from '../types';
import { Button } from '../ui/button';

interface NavigationProps {
  currentPage: PageKey;
  onNavigate: (page: PageKey) => void;
}

const navLinks: Array<{ key: PageKey; label: string; icon: JSX.Element; desc: string }> = [
  { key: 'onboarding', label: 'Intake', icon: <Upload className="h-4 w-4" />, desc: 'Upload docs' },
  {
    key: 'tasks',
    label: 'Task Builder',
    icon: <ClipboardList className="h-4 w-4" />,
    desc: 'Generated rules',
  },
  {
    key: 'monitor',
    label: 'PR Monitor',
    icon: <GitBranch className="h-4 w-4" />,
    desc: 'Agent runs',
  },
];

export function Navigation({ currentPage, onNavigate }: NavigationProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-base/95 px-6 py-5">
      <div className="mx-auto flex max-w-6xl items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="h-5 w-5 text-text" />
          <span className="text-sm font-semibold tracking-[0.35em] text-text">GUARDIANS</span>
        </div>
        <nav className="flex items-center gap-2 text-sm font-medium text-textMuted">
          {navLinks.map((link) => {
            const active = currentPage === link.key;
            return (
              <button
                key={link.key}
                type="button"
                onClick={() => onNavigate(link.key)}
                className={`rounded-full px-4 py-2 transition ${
                  active
                    ? 'text-text bg-panelMuted'
                    : 'hover:text-text'
                }`}
              >
                {link.label}
              </button>
            );
          })}
        </nav>
        <div className="flex items-center gap-3 text-sm text-textMuted">
          <button type="button" className="hover:text-text">
            Log in
          </button>
          <Button variant="outline">Sign up</Button>
        </div>
      </div>
    </header>
  );
}
