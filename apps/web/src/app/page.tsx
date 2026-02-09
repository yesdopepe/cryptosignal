'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  TrendingUp, 
  Radio, 
  Bell, 
  Shield, 
  Zap, 
  BarChart3,
  ArrowRight,
  Sparkles,
  Globe,
  Lock
} from 'lucide-react';

export default function LandingPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Redirect logged in users to dashboard
  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (isAuthenticated) {
    return null; // Will redirect
  }

  const features = [
    {
      icon: Radio,
      title: 'Real-time Signals',
      description: 'Get instant notifications when new tokens are detected from Telegram channels.',
      color: 'text-blue-500',
      bgColor: 'bg-blue-500/10',
    },
    {
      icon: TrendingUp,
      title: 'Price Tracking',
      description: 'Track token prices, 24h changes, volume, and liquidity in real-time.',
      color: 'text-green-500',
      bgColor: 'bg-green-500/10',
    },
    {
      icon: Bell,
      title: 'Smart Notifications',
      description: 'Get notified via email or Telegram when tracked tokens have significant moves.',
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-500/10',
    },
    {
      icon: BarChart3,
      title: 'Live Dashboard',
      description: 'View trending tokens, tracked prices, and real-time market data at a glance.',
      color: 'text-purple-500',
      bgColor: 'bg-purple-500/10',
    },
    {
      icon: Globe,
      title: 'Multichain Support',
      description: 'Support for Ethereum, BSC, Solana, and other major chains.',
      color: 'text-cyan-500',
      bgColor: 'bg-cyan-500/10',
    },
    {
      icon: Lock,
      title: 'Secure & Private',
      description: 'Your data is encrypted and your tracking preferences are completely private.',
      color: 'text-pink-500',
      bgColor: 'bg-pink-500/10',
    },
  ];

  return (
    <div className="space-y-16 py-8">
      {/* Hero Section */}
      <section className="text-center space-y-6">
        <Badge variant="outline" className="px-4 py-1.5">
          <Sparkles className="h-3 w-3 mr-2" />
          Powered by Advanced Analysis
        </Badge>
        
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
          Track Crypto Signals
          <br />
          <span className="text-primary">Before They Moon</span>
        </h1>
        
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Aggregate signals from Telegram channels. 
          Track new tokens, monitor prices, and get notified before the pump.
        </p>
        
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
          <Link href="/register">
            <Button size="lg" className="gap-2 w-full sm:w-auto">
              Get Started Free
              <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/login">
            <Button variant="outline" size="lg" className="w-full sm:w-auto">
              Sign In
            </Button>
          </Link>
        </div>
      </section>

      {/* Stats Preview */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-primary">24/7</p>
            <p className="text-sm text-muted-foreground">Real-time Monitoring</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-green-500">1000+</p>
            <p className="text-sm text-muted-foreground">Tokens Tracked</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-yellow-500">10s</p>
            <p className="text-sm text-muted-foreground">Update Interval</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-6 text-center">
            <p className="text-3xl font-bold text-purple-500">Free</p>
            <p className="text-sm text-muted-foreground">To Get Started</p>
          </CardContent>
        </Card>
      </section>

      {/* Features Grid */}
      <section className="space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Everything You Need</h2>
          <p className="text-muted-foreground mt-2">Powerful tools to track and analyze crypto signals</p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title} className="hover:border-primary/50 transition-colors">
                <CardContent className="p-6 space-y-4">
                  <div className={`p-3 rounded-lg w-fit ${feature.bgColor}`}>
                    <Icon className={`h-6 w-6 ${feature.color}`} />
                  </div>
                  <h3 className="font-semibold text-lg">{feature.title}</h3>
                  <p className="text-sm text-muted-foreground">{feature.description}</p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* How It Works */}
      <section className="space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">How It Works</h2>
          <p className="text-muted-foreground mt-2">Get started in three simple steps</p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 text-primary font-bold text-xl flex items-center justify-center mx-auto">
              1
            </div>
            <h3 className="font-semibold text-lg">Create Account</h3>
            <p className="text-sm text-muted-foreground">
              Sign up for free and connect your Telegram account to monitor your channels.
            </p>
          </div>
          <div className="text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 text-primary font-bold text-xl flex items-center justify-center mx-auto">
              2
            </div>
            <h3 className="font-semibold text-lg">Track Tokens</h3>
            <p className="text-sm text-muted-foreground">
              Search and track tokens you're interested in. We'll monitor prices and signals for you.
            </p>
          </div>
          <div className="text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-primary/10 text-primary font-bold text-xl flex items-center justify-center mx-auto">
              3
            </div>
            <h3 className="font-semibold text-lg">Get Notified</h3>
            <p className="text-sm text-muted-foreground">
              Receive instant notifications when there's activity on your tracked tokens.
            </p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="text-center py-12 px-6 rounded-2xl bg-gradient-to-r from-primary/10 via-purple-500/10 to-pink-500/10 border">
        <h2 className="text-2xl md:text-3xl font-bold mb-4">
          Ready to catch the next gem?
        </h2>
        <p className="text-muted-foreground mb-6 max-w-lg mx-auto">
          Join now and start tracking crypto signals in real-time. It's free to get started.
        </p>
        <Link href="/register">
          <Button size="lg" className="gap-2">
            <Zap className="h-4 w-4" />
            Start Tracking Now
          </Button>
        </Link>
      </section>
    </div>
  );
}
