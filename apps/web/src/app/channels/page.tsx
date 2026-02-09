"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  useUserTelegramChannels,
  useSubscriptions,
  useSubscribe,
  useUnsubscribe,
  useUpdateSubscription,
  useUserTelegramStatus,
  useMonitoringStatus,
  useStartMonitoring,
  useStopMonitoring,
  useRefreshMonitoring,
} from "@/hooks/useApi";
import { useDataTable } from "@/hooks/useDataTable";
import { DataTable, Column } from "@/components/common/data-table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Loader2,
  Radio,
  Users,
  Check,
  Plus,
  Bell,
  Mail,
  MessageSquare,
  BellOff,
  Link as LinkIcon,
  AlertCircle,
  Play,
  Square,
  RefreshCw,
  Activity,
  Eye,
  Zap,
  Clock,
} from "lucide-react";
import type { UserChannel, ChannelSubscription } from "@/lib/api";

function MonitoringCard() {
  const { data: monitoring, isLoading } = useMonitoringStatus();
  const startMutation = useStartMonitoring();
  const stopMutation = useStopMonitoring();
  const refreshMutation = useRefreshMonitoring();

  const isMonitoring = monitoring?.is_monitoring ?? false;
  const isPending =
    startMutation.isPending ||
    stopMutation.isPending ||
    refreshMutation.isPending;

  const timeAgo = (dateStr?: string | null) => {
    if (!dateStr) return "Never";
    const diff = Date.now() - new Date(dateStr).getTime();
    const secs = Math.floor(diff / 1000);
    if (secs < 60) return `${secs}s ago`;
    const mins = Math.floor(secs / 60);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <Card
      className={
        isMonitoring ? "border-green-500/30 bg-green-500/5" : "border-border/50"
      }
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className={`p-2 rounded-lg ${isMonitoring ? "bg-green-500/10" : "bg-muted"}`}
            >
              <Activity
                className={`h-5 w-5 ${isMonitoring ? "text-green-500" : "text-muted-foreground"}`}
              />
            </div>
            <div>
              <CardTitle className="text-lg">Background Monitoring</CardTitle>
              <CardDescription>
                {isMonitoring
                  ? "Listening for messages from your subscribed channels"
                  : "Start monitoring to automatically detect signals"}
              </CardDescription>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {isMonitoring && (
              <Badge variant="success" className="gap-1.5">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
                </span>
                Active
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Stats */}
        {monitoring && isMonitoring && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="flex items-center gap-2 p-2 rounded-lg bg-secondary/50">
              <Eye className="h-4 w-4 text-muted-foreground shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Channels</p>
                <p className="text-sm font-semibold">
                  {monitoring.channels_count}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-secondary/50">
              <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Messages</p>
                <p className="text-sm font-semibold">
                  {monitoring.messages_processed}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-secondary/50">
              <Zap className="h-4 w-4 text-muted-foreground shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Signals</p>
                <p className="text-sm font-semibold">
                  {monitoring.signals_detected}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 p-2 rounded-lg bg-secondary/50">
              <Clock className="h-4 w-4 text-muted-foreground shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Last Msg</p>
                <p className="text-sm font-semibold">
                  {timeAgo(monitoring.last_message_at)}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center gap-2">
          {isMonitoring ? (
            <>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => stopMutation.mutate()}
                disabled={isPending}
              >
                {stopMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <Square className="h-4 w-4 mr-2" />
                )}
                Stop Monitoring
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => refreshMutation.mutate()}
                disabled={isPending}
              >
                {refreshMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <RefreshCw className="h-4 w-4 mr-2" />
                )}
                Refresh Channels
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              onClick={() => startMutation.mutate()}
              disabled={isPending}
            >
              {startMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Play className="h-4 w-4 mr-2" />
              )}
              Start Monitoring
            </Button>
          )}
        </div>

        {/* Errors */}
        {monitoring?.errors && monitoring.errors.length > 0 && (
          <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
            <p className="text-xs font-medium text-destructive mb-1">
              Recent Errors
            </p>
            {monitoring.errors.slice(-3).map((err, i) => (
              <p key={i} className="text-xs text-destructive/80 truncate">
                {err}
              </p>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ChannelsPage() {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();

  const { data: telegramStatus } = useUserTelegramStatus();
  const { data: channelsData, isLoading: channelsLoading } =
    useUserTelegramChannels();
  const { data: subsData, isLoading: subsLoading } = useSubscriptions();

  const subscribeMutation = useSubscribe();
  const unsubscribeMutation = useUnsubscribe();
  const updateSubscriptionMutation = useUpdateSubscription();

  // Redirect if not authenticated
  if (!authLoading && !isAuthenticated) {
    router.push("/login");
    return null;
  }

  const isTelegramConnected = telegramStatus?.connected;
  const subscriptions = subsData?.subscriptions || [];
  const channels = channelsData?.channels || [];

  // Helper to check if a channel is subscribed
  const isSubscribed = (channelId: number) => {
    return subscriptions.some((s) => s.channel_id === channelId && s.is_active);
  };

  // Directory Columns
  const directoryColumns: Column<UserChannel>[] = [
    {
      header: "Name",
      accessorKey: "title",
      cell: (channel) => (
        <div className="flex items-center gap-3">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
              channel.is_channel ? "bg-blue-500/10" : "bg-green-500/10"
            }`}
          >
            {channel.is_channel ? (
              <Radio className="h-4 w-4 text-blue-500" />
            ) : (
              <Users className="h-4 w-4 text-green-500" />
            )}
          </div>
          <div className="flex flex-col">
            <span
              className="font-medium truncate max-w-[200px]"
              title={channel.title}
            >
              {channel.title}
            </span>
            {channel.username && (
              <span className="text-xs text-muted-foreground">
                @{channel.username}
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      header: "Type",
      cell: (channel) => (
        <Badge variant="outline" className="text-xs">
          {channel.is_channel ? "Channel" : "Group"}
        </Badge>
      ),
    },
    {
      header: "Members",
      accessorKey: "participants_count",
      cell: (channel) =>
        channel.participants_count
          ? channel.participants_count.toLocaleString()
          : "-",
      className: "text-right",
    },
    {
      header: "Action",
      cell: (channel) => {
        const subscribed = isSubscribed(channel.id);
        return (
          <div className="flex justify-end">
            {subscribed ? (
              <Badge variant="success" className="gap-1">
                <Check className="h-3 w-3" />
                Tracking
              </Badge>
            ) : (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  subscribeMutation.mutate({
                    channel_id: channel.id,
                    channel_title: channel.title,
                    notify_telegram: true,
                  })
                }
                disabled={subscribeMutation.isPending}
              >
                {subscribeMutation.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <>
                    <Plus className="h-3 w-3 mr-1" />
                    Track
                  </>
                )}
              </Button>
            )}
          </div>
        );
      },
      className: "text-right",
    },
  ];

  // Subscriptions Columns
  const subscriptionColumns: Column<ChannelSubscription>[] = [
    {
      header: "Channel",
      accessorKey: "channel_name",
      cell: (sub) => (
        <div className="font-medium">
          {sub.channel_name || `Channel ${sub.channel_id}`}
        </div>
      ),
    },
    {
      header: "Notifications",
      cell: (sub) => (
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className={
              sub.notify_telegram ? "text-primary" : "text-muted-foreground"
            }
            onClick={() =>
              updateSubscriptionMutation.mutate({
                id: sub.id,
                data: { notify_telegram: !sub.notify_telegram },
              })
            }
          >
            <MessageSquare className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className={
              sub.notify_email ? "text-primary" : "text-muted-foreground"
            }
            onClick={() =>
              updateSubscriptionMutation.mutate({
                id: sub.id,
                data: { notify_email: !sub.notify_email },
              })
            }
          >
            <Mail className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
    {
      header: "Status",
      cell: (sub) => (
        <Badge variant={sub.is_active ? "success" : "secondary"}>
          {sub.is_active ? "Active" : "Paused"}
        </Badge>
      ),
    },
    {
      header: "Actions",
      cell: (sub) => (
        <div className="flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={() => unsubscribeMutation.mutate(sub.id)}
            disabled={unsubscribeMutation.isPending}
          >
            <BellOff className="h-4 w-4 mr-2" />
            Unsubscribe
          </Button>
        </div>
      ),
      className: "text-right",
    },
  ];

  // Client-side pagination hooks
  const directoryPagination = useDataTable({ initialPageSize: 10 });
  const subscriptionPagination = useDataTable({ initialPageSize: 10 });

  // Slice data for validation
  const paginatedChannels = channels.slice(
    directoryPagination.offset,
    directoryPagination.offset! + directoryPagination.limit!,
  );
  const paginatedSubscriptions = subscriptions.slice(
    subscriptionPagination.offset,
    subscriptionPagination.offset! + subscriptionPagination.limit!,
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold tracking-tight">Channels</h1>
        <p className="text-muted-foreground">
          Manage your channel subscriptions and discover new signal sources.
        </p>
      </div>

      {!isTelegramConnected ? (
        <Card className="border-yellow-500/50 bg-yellow-500/5">
          <CardContent className="pt-6">
            <div className="flex items-start gap-4">
              <div className="p-2 rounded-full bg-yellow-500/10">
                <AlertCircle className="h-5 w-5 text-yellow-500" />
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-yellow-500">
                  Telegram Not Connected
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  Connect your Telegram account to browse and subscribe to
                  channels
                </p>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={() => router.push("/settings")}
                >
                  <LinkIcon className="h-4 w-4 mr-2" />
                  Connect Telegram
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {/* Background Monitoring Status */}
          <MonitoringCard />

          <Tabs defaultValue="subscriptions" className="space-y-4">
            <TabsList>
              <TabsTrigger value="subscriptions">My Subscriptions</TabsTrigger>
              <TabsTrigger value="directory">Channel Directory</TabsTrigger>
            </TabsList>

            <TabsContent value="subscriptions" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Active Subscriptions</CardTitle>
                  <CardDescription>
                    Channels you are currently tracking signals from.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <DataTable
                    columns={subscriptionColumns}
                    data={paginatedSubscriptions}
                    isLoading={subsLoading}
                    pagination={{
                      ...subscriptionPagination,
                      totalItems: subscriptions.length,
                      onPageChange: subscriptionPagination.setPage,
                    }}
                    emptyMessage="You haven't subscribed to any channels yet."
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="directory" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Available Channels</CardTitle>
                  <CardDescription>
                    All channels and groups discovered from your Telegram
                    account.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <DataTable
                    columns={directoryColumns}
                    data={paginatedChannels}
                    isLoading={channelsLoading}
                    pagination={{
                      ...directoryPagination,
                      totalItems: channels.length,
                      onPageChange: directoryPagination.setPage,
                    }}
                    emptyMessage="No channels found in your Telegram account."
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}
    </div>
  );
}
