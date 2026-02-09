'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Activity, BarChart3, Radio, Settings, Menu, User, LogIn, LogOut, Bell, MessageSquare, Check, Trash2, ExternalLink, Search } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useAuth } from '@/lib/auth-context';
import { useNotificationBadge, useNotifications, useMarkAllRead, useMarkNotificationsRead } from '@/hooks/useNotifications';
import { cn, getChainUrl } from '@/lib/utils';
import { useState, useRef, useEffect, useCallback } from 'react';
import { useExplorer } from '@/hooks/useExplorer'; // Add this

const navLinks = [
  { href: '/dashboard', label: 'Dashboard', icon: Activity, requiresAuth: true },
  { href: '/explore', label: 'Explore', icon: Search, requiresAuth: true },
  { href: '/channels', label: 'My Channels', icon: MessageSquare, requiresAuth: true },
  { href: '/notifications', label: 'Notifications', icon: Bell, requiresAuth: true },
  { href: '/settings', label: 'Settings', icon: Settings, requiresAuth: true },
];

function NotificationBell() {
  const { data: badge } = useNotificationBadge();
  const { data: recentNotifs } = useNotifications({ limit: 5, unread_only: true });
  const markAllRead = useMarkAllRead();
  const markRead = useMarkNotificationsRead();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  const unreadCount = badge?.unread_count ?? 0;
  const notifications = recentNotifs?.notifications ?? [];
  const { openExplorer } = useExplorer(); // Add hook usage

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const timeAgo = (dateStr: string) => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'now';
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    return `${Math.floor(hrs / 24)}d`;
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <Button
        variant="ghost"
        size="icon"
        className="relative"
        onClick={() => setOpen(!open)}
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
          </span>
        )}
      </Button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-96 rounded-xl border border-border/40 bg-background/95 backdrop-blur-xl shadow-2xl z-[60] overflow-hidden ring-1 ring-black/5 animate-in fade-in zoom-in-95 duration-200">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/40 bg-muted/20">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Bell className="h-4 w-4 text-primary" />
              Latest Detections
            </h3>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 text-xs text-muted-foreground hover:text-primary"
                  onClick={() => markAllRead.mutate()}
                >
                  <Check className="h-3 w-3 mr-1" />
                  Mark read
                </Button>
              )}
            </div>
          </div>

          {/* Notification items */}
          <div className="max-h-[28rem] overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="px-4 py-12 text-center text-sm text-muted-foreground flex flex-col items-center gap-3">
                <div className="h-12 w-12 rounded-full bg-muted/50 flex items-center justify-center">
                    <Bell className="h-5 w-5 opacity-40" />
                </div>
                <p>No new detections</p>
              </div>
            ) : (
              notifications.map((notif: any) => {
                const data = notif.data || {};
                const token = notif.token_symbol || data.token_symbol || 'Unknown';
                const ca = notif.contract_address || data.contract_addresses?.[0];
                const chain = data.chain;
                
                return (
                  <div
                    key={notif.id}
                    className={cn(
                      'group relative px-4 py-4 border-b border-border/20 transition-all hover:bg-muted/30 cursor-pointer',
                      !notif.is_read && 'bg-primary/5'
                    )}
                    onClick={() => {
                        markRead.mutate([notif.id]);
                        setOpen(false);
                        router.push('/notifications');
                    }}
                  >
                    {!notif.is_read && (
                      <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-primary/70" />
                    )}
                    
                    <div className="flex gap-3">
                      {/* Icon Box */}
                      <div className="shrink-0 mt-0.5">
                         <div className={cn(
                             "h-9 w-9 rounded-full flex items-center justify-center border transition-colors",
                             "bg-background/80 border-border/40 text-primary shadow-sm"
                         )}>
                             <Radio className="h-4 w-4" />
                         </div>
                      </div>

                      <div className="flex-1 min-w-0 space-y-1">
                        {/* Title Row */}
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-medium leading-none">
                            Contract Detected
                          </p>
                          <span className="text-[10px] text-muted-foreground font-mono">
                            {timeAgo(notif.created_at)}
                          </span>
                        </div>
                        
                        {/* Token Info */}
                        <div className="flex items-center gap-2 mt-1.5">
                           <Badge variant="outline" className="font-mono text-[10px] px-1.5 h-5 bg-background/50">
                              {token}
                           </Badge>
                           {chain && (
                               <span className="text-[10px] uppercase text-muted-foreground font-medium">
                                   {chain}
                               </span>
                           )}
                           <span className="text-[10px] text-muted-foreground truncate max-w-[120px]">
                               • {notif.channel_name || data.channel}
                           </span>
                        </div>

                        {/* Contract Address Preview */}
                        {ca && (
                            <div className="flex items-center gap-1 mt-2">
                                <div className="flex-1 flex items-center bg-muted/40 rounded-md border border-border/40 overflow-hidden">
                                    <code className="text-[10px] font-mono text-muted-foreground/80 truncate px-2 py-1">
                                        {ca}
                                    </code>
                                </div>
                                <Link 
                                    href={getChainUrl(chain, ca)}
                                    className="h-6 w-6 flex items-center justify-center rounded-md border border-border/40 bg-muted/30 text-muted-foreground hover:text-foreground hover:bg-muted/50"
                                    onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        openExplorer(chain, ca);
                                    }}
                                >
                                    <ExternalLink className="h-3 w-3" />
                                </Link>
                            </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <Link
            href="/notifications"
            className="flex items-center justify-center w-full py-3 text-xs font-medium bg-muted/10 border-t border-border/40 hover:bg-muted/30 transition-colors text-muted-foreground hover:text-foreground"
            onClick={() => setOpen(false)}
          >
            View all detections
            <ExternalLink className="h-3 w-3 ml-2 opacity-50" />
          </Link>
        </div>
      )}
    </div>
  );
}

export function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { isConnected, signals } = useWebSocket();
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const filteredLinks = navLinks.filter(link => !link.requiresAuth || isAuthenticated);

  const handleLogout = async () => {
    await logout();
    router.push('/');
  };

  return (
    <header className="sticky top-0 z-50 w-full mb-4 glass">
      <div className="container flex h-16 items-center">
        {/* Logo */}
        <div className="mr-6 flex items-center gap-2">
          <Link href="/" className="flex items-center gap-2 text-xl font-bold font-mono tracking-tighter">
            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center border border-primary/50 text-primary">
              <Activity className="h-5 w-5" />
            </div>
            <span className="bg-gradient-to-r from-white to-white/70 bg-clip-text text-transparent">
              CryptoSignal
            </span>
          </Link>
        </div>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center gap-6 flex-1">
          {filteredLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  'flex items-center gap-2 text-sm font-medium transition-colors hover:text-foreground/80',
                  isActive ? 'text-foreground' : 'text-foreground/60'
                )}
              >
                <Icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Right side */}
        <div className="flex items-center gap-4 ml-auto">
          {/* Connection status */}
          <div className="hidden sm:flex items-center gap-2">
            {isConnected ? (
              <Badge variant="success" className="flex items-center gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                </span>
                Live
              </Badge>
            ) : (
              <Badge variant="secondary">Offline</Badge>
            )}
          </div>

          {/* Notification bell with dropdown */}
          {isAuthenticated && <NotificationBell />}

          {/* User Auth */}
          {!isLoading && (
            <div className="hidden md:flex items-center gap-2">
              {isAuthenticated && user ? (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <User className="h-4 w-4" />
                    <span>{user.username}</span>
                  </div>
                  <Button variant="ghost" size="sm" onClick={handleLogout}>
                    <LogOut className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <Link href="/login">
                    <Button variant="ghost" size="sm">
                      <LogIn className="h-4 w-4 mr-2" />
                      Login
                    </Button>
                  </Link>
                  <Link href="/register">
                    <Button size="sm">
                      Sign Up
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          )}

          {/* Mobile menu button */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <nav className="md:hidden border-t p-4 space-y-2">
          {filteredLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors',
                  isActive 
                    ? 'bg-secondary text-foreground' 
                    : 'text-foreground/60 hover:bg-secondary/50 hover:text-foreground'
                )}
              >
                <Icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
          
          {/* Mobile status & auth */}
          <div className="flex flex-col gap-2 px-3 pt-2 border-t mt-2">
            <div className="flex items-center gap-2">
              {isConnected ? (
                <Badge variant="success" className="flex items-center gap-1.5">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500"></span>
                  </span>
                  Live
                </Badge>
              ) : (
                <Badge variant="secondary">Offline</Badge>
              )}
              <Badge variant="outline">{signals.length} signals</Badge>
            </div>
            
            {/* Mobile auth buttons */}
            {!isLoading && (
              <div className="flex items-center gap-2 pt-2">
                {isAuthenticated && user ? (
                  <>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground flex-1">
                      <User className="h-4 w-4" />
                      <span>{user.username}</span>
                    </div>
                    <Button variant="ghost" size="sm" onClick={handleLogout}>
                      <LogOut className="h-4 w-4 mr-2" />
                      Logout
                    </Button>
                  </>
                ) : (
                  <>
                    <Link href="/login" className="flex-1" onClick={() => setMobileMenuOpen(false)}>
                      <Button variant="ghost" size="sm" className="w-full">
                        Login
                      </Button>
                    </Link>
                    <Link href="/register" className="flex-1" onClick={() => setMobileMenuOpen(false)}>
                      <Button size="sm" className="w-full">
                        Sign Up
                      </Button>
                    </Link>
                  </>
                )}
              </div>
            )}
          </div>
        </nav>
      )}
    </header>
  );
}
