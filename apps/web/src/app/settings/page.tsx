'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import {
  getUserTelegramStatus,
  connectUserTelegram,
  verifyUserTelegramCode,
  verifyUserTelegram2FA,
  disconnectUserTelegram,
  runBenchmark,
  type UserTelegramStatus,
  type BenchmarkResult,
} from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { toast } from '@/components/ui/use-toast';
import { 
  Phone, 
  Key, 
  Shield, 
  LogOut, 
  CheckCircle, 
  AlertCircle, 
  Radio, 
  Lock, 
  User,
  Loader2,
  Link as LinkIcon,
  Activity,
  Zap,
  Server,
  BarChart,
} from 'lucide-react';

export default function SettingsPage() {
  const { user, isAuthenticated, isLoading: authLoading, logout } = useAuth();
  const router = useRouter();
  
  const [phoneNumber, setPhoneNumber] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [twoFAPassword, setTwoFAPassword] = useState('');
  const [telegramStatus, setTelegramStatus] = useState<UserTelegramStatus | null>(null);
  
  const [isBenchmarking, setIsBenchmarking] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkResult | null>(null);
  
  const [isLoading, setIsLoading] = useState(false);
  const [isPending, setIsPending] = useState(false);

  // Load Telegram status
  useEffect(() => {
    if (isAuthenticated) {
      loadTelegramStatus();
    }
  }, [isAuthenticated]);

  const loadTelegramStatus = async () => {
    try {
      const status = await getUserTelegramStatus();
      setTelegramStatus(status);
    } catch (error) {
      console.error('Failed to load Telegram status:', error);
    }
  };

  const handleRunBenchmark = async () => {
    setIsBenchmarking(true);
    try {
      const result = await runBenchmark();
      setBenchmarkResult(result);
      toast({ title: 'Success', description: 'Performance benchmark completed', variant: 'success' });
    } catch (error: any) {
      toast({ title: 'Error', description: 'Failed to run benchmark', variant: 'destructive' });
    } finally {
      setIsBenchmarking(false);
    }
  };

  const handleConnectTelegram = async () => {
    if (!phoneNumber) {
      toast({ title: 'Error', description: 'Please enter a phone number', variant: 'destructive' });
      return;
    }
    
    setIsPending(true);
    try {
      const result = await connectUserTelegram(phoneNumber);
      if (result.success) {
        toast({ title: 'Success', description: result.message, variant: 'success' });
        await loadTelegramStatus();
      } else {
        toast({ title: 'Error', description: result.error, variant: 'destructive' });
      }
    } catch (error: any) {
      toast({ title: 'Error', description: error.message || 'Failed to send verification code', variant: 'destructive' });
    } finally {
      setIsPending(false);
    }
  };

  const handleVerifyCode = async () => {
    if (!verificationCode) {
      toast({ title: 'Error', description: 'Please enter the verification code', variant: 'destructive' });
      return;
    }
    
    setIsPending(true);
    try {
      const result = await verifyUserTelegramCode(verificationCode);
      if (result.success) {
        toast({ title: 'Success', description: result.message, variant: 'success' });
        setVerificationCode('');
        await loadTelegramStatus();
      } else {
        toast({ title: 'Error', description: result.error, variant: 'destructive' });
      }
    } catch (error: any) {
      toast({ title: 'Error', description: error.message || 'Failed to verify code', variant: 'destructive' });
    } finally {
      setIsPending(false);
    }
  };

  const handleVerify2FA = async () => {
    if (!twoFAPassword) {
      toast({ title: 'Error', description: 'Please enter your 2FA password', variant: 'destructive' });
      return;
    }
    
    setIsPending(true);
    try {
      const result = await verifyUserTelegram2FA(twoFAPassword);
      if (result.success) {
        toast({ title: 'Success', description: result.message, variant: 'success' });
        setTwoFAPassword('');
        await loadTelegramStatus();
      } else {
        toast({ title: 'Error', description: result.error, variant: 'destructive' });
      }
    } catch (error: any) {
      toast({ title: 'Error', description: error.message || 'Failed to verify 2FA', variant: 'destructive' });
    } finally {
      setIsPending(false);
    }
  };

  const handleDisconnect = async () => {
    setIsPending(true);
    try {
      await disconnectUserTelegram();
      toast({ title: 'Success', description: 'Disconnected from Telegram', variant: 'success' });
      setPhoneNumber('');
      await loadTelegramStatus();
    } catch (error: any) {
      toast({ title: 'Error', description: error.message || 'Failed to disconnect', variant: 'destructive' });
    } finally {
      setIsPending(false);
    }
  };

  const getAuthStateDescription = () => {
    switch (telegramStatus?.auth_state) {
      case 'not_connected':
        return 'Enter your phone number to connect Telegram';
      case 'awaiting_code':
        return 'A verification code has been sent to your phone';
      case 'awaiting_2fa':
        return 'Please enter your 2FA password';
      case 'connected':
        return 'Your Telegram is connected';
      case 'error':
        return telegramStatus.error || 'Connection error occurred';
      default:
        return 'Check your connection status';
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account and Telegram connection
          </p>
        </div>
        {isAuthenticated && telegramStatus && (
          <Badge
            variant={telegramStatus.auth_state === 'connected' ? 'success' : 'secondary'}
            className="text-sm py-1"
          >
            {telegramStatus.auth_state === 'connected' ? 'Telegram Connected' : 'Telegram Not Connected'}
          </Badge>
        )}
      </div>

      {/* Account Card */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <User className="h-5 w-5" />
                Account
              </CardTitle>
              <CardDescription className="mt-1">
                {isAuthenticated 
                  ? `Logged in as ${user?.username}` 
                  : 'Sign in to connect your Telegram'}
              </CardDescription>
            </div>
            {isAuthenticated && (
              <Badge variant="success">Authenticated</Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isAuthenticated ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 rounded-lg bg-secondary">
                  <div className="text-sm text-muted-foreground">Username</div>
                  <div className="font-medium">{user?.username}</div>
                </div>
                <div className="p-3 rounded-lg bg-secondary">
                  <div className="text-sm text-muted-foreground">Email</div>
                  <div className="font-medium">{user?.email}</div>
                </div>
              </div>
              <Button variant="outline" onClick={() => logout()}>
                <LogOut className="h-4 w-4 mr-2" />
                Logout
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Create an account or sign in to connect your Telegram and track channels.
              </p>
              <div className="flex gap-2">
                <Button onClick={() => router.push('/login')}>
                  Sign In
                </Button>
                <Button variant="outline" onClick={() => router.push('/register')}>
                  Create Account
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* User Telegram Connection Card */}
      {isAuthenticated && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <LinkIcon className="h-5 w-5" />
                  Your Telegram Connection
                </CardTitle>
                <CardDescription className="mt-1">
                  {getAuthStateDescription()}
                </CardDescription>
              </div>
              {telegramStatus && (
                <Badge 
                  variant={telegramStatus.auth_state === 'connected' ? 'success' : 
                           telegramStatus.auth_state === 'error' ? 'danger' : 'warning'}
                >
                  {telegramStatus.auth_state}
                </Badge>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Connected State */}
            {telegramStatus?.auth_state === 'connected' && (
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-green-500">
                  <CheckCircle className="h-5 w-5" />
                  <span className="font-medium">Telegram Connected!</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="p-3 rounded-lg bg-secondary">
                    <div className="text-sm text-muted-foreground">Phone</div>
                    <div className="font-medium">{telegramStatus.phone_number || 'N/A'}</div>
                  </div>
                  {telegramStatus.username && (
                    <div className="p-3 rounded-lg bg-secondary">
                      <div className="text-sm text-muted-foreground">Username</div>
                      <div className="font-medium">@{telegramStatus.username}</div>
                    </div>
                  )}
                  {telegramStatus.first_name && (
                    <div className="p-3 rounded-lg bg-secondary">
                      <div className="text-sm text-muted-foreground">Name</div>
                      <div className="font-medium">
                        {telegramStatus.first_name} {telegramStatus.last_name || ''}
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button onClick={() => router.push('/channels')}>
                    <Radio className="h-4 w-4 mr-2" />
                    Browse Channels
                  </Button>
                  <Button variant="destructive" onClick={handleDisconnect} disabled={isPending}>
                    <LogOut className="h-4 w-4 mr-2" />
                    {isPending ? 'Disconnecting...' : 'Disconnect'}
                  </Button>
                </div>
              </div>
            )}

            {/* Not Connected - Phone Number Step */}
            {(!telegramStatus || telegramStatus.auth_state === 'not_connected' || telegramStatus.auth_state === 'error') && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Phone className="h-4 w-4" />
                  Step 1: Enter Phone Number
                </div>
                <div className="flex gap-2">
                  <input
                    type="tel"
                    placeholder="+1234567890"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-md border bg-background text-sm"
                  />
                  <Button onClick={handleConnectTelegram} disabled={isPending || !phoneNumber}>
                    {isPending ? 'Sending...' : 'Send Code'}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Enter your phone number in international format (e.g., +1234567890)
                </p>
              </div>
            )}

            {/* Awaiting Code Step */}
            {telegramStatus?.auth_state === 'awaiting_code' && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Key className="h-4 w-4" />
                  Step 2: Enter Verification Code
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="12345"
                    value={verificationCode}
                    onChange={(e) => setVerificationCode(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-md border bg-background text-sm"
                    maxLength={6}
                  />
                  <Button onClick={handleVerifyCode} disabled={isPending || !verificationCode}>
                    {isPending ? 'Verifying...' : 'Verify'}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Enter the code sent to your Telegram app
                </p>
              </div>
            )}

            {/* Awaiting 2FA Step */}
            {telegramStatus?.auth_state === 'awaiting_2fa' && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Shield className="h-4 w-4" />
                  Step 3: Enter 2FA Password
                </div>
                <div className="flex gap-2">
                  <input
                    type="password"
                    placeholder="Your 2FA password"
                    value={twoFAPassword}
                    onChange={(e) => setTwoFAPassword(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-md border bg-background text-sm"
                  />
                  <Button onClick={handleVerify2FA} disabled={isPending || !twoFAPassword}>
                    {isPending ? 'Verifying...' : 'Verify'}
                  </Button>
                </div>
              </div>
            )}

            {/* Error State */}
            {telegramStatus?.auth_state === 'error' && telegramStatus.error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <div className="font-medium text-red-500">Error</div>
                  <p className="text-sm text-muted-foreground">{telegramStatus.error}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* System Performance & Benchmarks */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5" />
                System Performance
              </CardTitle>
              <CardDescription className="mt-1">
                Run server benchmarks and stress tests
              </CardDescription>
            </div>
            <Button 
              onClick={handleRunBenchmark} 
              disabled={isBenchmarking}
              variant="outline"
              size="sm"
            >
              {isBenchmarking ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Zap className="mr-2 h-4 w-4" />
                  Run Benchmark
                </>
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {!benchmarkResult ? (
            <div className="text-center py-6 text-muted-foreground">
              <Server className="h-12 w-12 mx-auto mb-3 opacity-20" />
              <p>Run a benchmark to analyze server response times and cache efficiency.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Cache Performance */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium flex items-center gap-2">
                    <Server className="h-4 w-4" /> Aggregation Performance (Leaderboard)
                  </h3>
                  <Badge variant={benchmarkResult.system_status.cache_connected ? "success" : "destructive"}>
                    Redis {benchmarkResult.system_status.cache_connected ? "Connected" : "Missing"}
                  </Badge>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
                    <div className="text-xs text-muted-foreground mb-1">Uncached (Complex DB Query)</div>
                    <div className="text-2xl font-bold text-orange-600">
                      {benchmarkResult.benchmark_results.response_time.uncached_ms} ms
                    </div>
                  </div>
                  <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                    <div className="text-xs text-muted-foreground mb-1">Cached (Redis Hit)</div>
                    <div className="text-2xl font-bold text-emerald-600">
                      {benchmarkResult.benchmark_results.response_time.cache_hit_ms} ms
                    </div>
                  </div>
                </div>
                
                <div className="p-3 rounded-lg bg-secondary flex items-center justify-between text-sm">
                  <span>Improvement Factor</span>
                  <span className="font-bold text-emerald-500">
                    {benchmarkResult.benchmark_results.response_time.improvement_factor}x faster
                  </span>
                </div>
              </div>
              
              <div className="border-t pt-4 space-y-3">
                <h3 className="text-sm font-medium flex items-center gap-2">
                  <BarChart className="h-4 w-4" /> Stress Test ({benchmarkResult.benchmark_results.stress_test.concurrent_requests} concurrent requests)
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div className="p-3 rounded-lg bg-secondary">
                    <div className="text-xs text-muted-foreground">Total Time</div>
                    <div className="font-medium">{benchmarkResult.benchmark_results.stress_test.total_time_ms} ms</div>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary">
                    <div className="text-xs text-muted-foreground">Avg / Request</div>
                    <div className="font-medium">{benchmarkResult.benchmark_results.stress_test.avg_time_per_request_ms} ms</div>
                  </div>
                  <div className="p-3 rounded-lg bg-secondary">
                    <div className="text-xs text-muted-foreground">Throughput</div>
                    <div className="font-medium">{benchmarkResult.benchmark_results.stress_test.requests_per_second} req/s</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
