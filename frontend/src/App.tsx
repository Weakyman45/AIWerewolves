import { useState, useEffect, useCallback, useRef } from 'react'

const API_BASE = 'http://localhost:8000/api'

const defaultPlayerNames = ['Alice', 'Bob', 'Charlie', 'David', 'Eve', 'Frank', 'Grace', 'Henry', 'Ivy']

type Player = {
  id: string
  name: string
  role: string
  is_alive: boolean
  is_sheriff?: boolean
  in_sheriff_election?: boolean
}

type GameStatus = {
  game_id: string
  status: string
  winner?: string | null
  players: Player[]
  current_round: number
  current_phase: string
  error?: string | null
  is_paused?: boolean
  strategy_version?: string | null
}

type GameLog = {
  timestamp: string
  type: string
  round_number?: number
  phase?: string
  winner?: string
  player_id?: string
  player_name?: string
  cause?: string
  content?: string
  action?: {
    actor?: string
    target?: string
    action?: string
    result?: string
  }
  vote?: {
    voter?: string
    target?: string
  }
  decision?: {
    decision_type?: string
    target_id?: string | null
    reasoning?: string
    raw_output?: string
  }
}

type StartGameResponse = {
  game_id: string
  strategy_version?: string | null
}

type VersionSummary = {
  version: string
  parent?: string | null
  created_at?: string | null
  status?: string | null
  accepted?: boolean | null
  focus?: string | null
  candidate_from?: string | null
  validated_at?: string | null
  improvement?: number | null
  promotion_summary?: string | null
  ab_result?: {
    version_a?: string
    version_b?: string
    total_games?: number
    successful_games?: number
    failed_games?: number
    a_wins?: number
    b_wins?: number
    a_win_rate?: number
    b_win_rate?: number
    better_version?: string | null
    skipped?: boolean
    reason?: string
    statistics?: {
      significant?: boolean
      p_value?: number
    }
  } | null
  test_games?: number
  win_rate?: {
    werewolves?: number
    villagers?: number
  }
  metrics?: {
    total_games?: number
    werewolf_win_rate?: number
    villager_win_rate?: number
  }
  analysis_summary?: {
    total_games?: number
    werewolf_win_rate?: number
    villager_win_rate?: number
    average_rounds?: number
    quality_metrics?: {
      counts?: {
        nonseer_claim_repairs?: number
        llm_fallbacks?: number
        unauthorized_werewolf_fake_seer_blocks?: number
        public_claim_consistency_repairs?: number
        total_rule_repairs?: number
      }
      total?: number
    }
  }
  training_summary?: {
    requested?: number
    completed?: number
    timed_out?: number
    failed?: number
  }
  changes?: string[]
}

type EvolutionStatus = {
  status: string
  is_running: boolean
  current_version?: string | null
  latest_pointer?: string | null
  version_count: number
  evolved_version_count: number
  current?: VersionSummary | null
  versions: VersionSummary[]
  latest_result?: {
    success?: boolean
    total_iterations?: number
    final_version?: string
    history?: Array<{
      iteration?: number
      timestamp?: string
      result?: {
        old_version?: string
        new_version?: string
        accepted?: boolean
        improvement?: number
        ab_result?: VersionSummary['ab_result']
      }
    }>
  } | null
  active_run?: {
    iteration?: number
    total_iterations?: number
    phase?: string
    initial_version?: string | null
    trigger_game_id?: string | null
    train_games?: number
    ab_games?: number
    game_runner?: string
  } | null
  history?: Array<{
    timestamp?: string | null
    initial_version?: string | null
    final_version?: string | null
    total_iterations?: number
    trigger_game_id?: string | null
  }>
  rubric_summary?: {
    loop_stage?: string
    latest_ab_result?: VersionSummary['ab_result'] | null
    latest_ab_version?: string | null
    current_promoted_by_ab?: boolean
    rollback_version_count?: number
    training_health?: {
      completed?: number
      timed_out?: number
      failed?: number
      has_runtime_issues?: boolean
    }
    bad_case_summary?: {
      nonseer_claim_repairs?: number
      llm_fallbacks?: number
      unauthorized_werewolf_fake_seer_blocks?: number
      public_claim_consistency_repairs?: number
    }
  }
  error?: string | null
}

const visibleLogKey = (log: GameLog) => JSON.stringify({
  type: log.type,
  round_number: log.round_number,
  phase: log.phase,
  winner: log.winner,
  player_id: log.player_id,
  player_name: log.player_name,
  cause: log.cause,
  content: log.content,
  action: log.action,
  vote: log.vote
})

const dedupeConsecutiveVisibleLogs = (items: GameLog[]) => {
  const visible = items.filter((log) => log.type !== 'agent_decision')
  const result: GameLog[] = []
  let previousKey = ''

  for (const log of visible) {
    const key = visibleLogKey(log)
    if (key === previousKey) continue
    result.push(log)
    previousKey = key
  }

  return result
}

function App() {
  const [gameId, setGameId] = useState<string | null>(null)
  const [gameStatus, setGameStatus] = useState<GameStatus | null>(null)
  const [logs, setLogs] = useState<GameLog[]>([])
  const [playerNames, setPlayerNames] = useState<string[]>(defaultPlayerNames)
  const [isLoading, setIsLoading] = useState(false)
  const [isRunLoading, setIsRunLoading] = useState(false)
  const [evolutionStatus, setEvolutionStatus] = useState<EvolutionStatus | null>(null)
  const [isEvolutionLoading, setIsEvolutionLoading] = useState(false)
  const [autoEvolveAfterGame, setAutoEvolveAfterGame] = useState(true)
  const autoEvolutionTriggeredGameIdRef = useRef<string | null>(null)

  const fetchEvolutionStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/evolution/status`)
      const data = await response.json() as EvolutionStatus
      setEvolutionStatus(data)
    } catch (error) {
      console.error('Error fetching evolution status:', error)
    }
  }, [])

  const startNewGame = async () => {
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE}/game/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_names: playerNames })
      })
      const data = await response.json() as StartGameResponse
      setGameId(data.game_id)
      void fetchEvolutionStatus()
    } catch (error) {
      console.error('Error starting game:', error)
      alert('创建游戏失败，请检查后端是否启动')
    }
    setIsLoading(false)
  }

  const runGame = async () => {
    if (!gameId || isRunLoading || gameStatus?.status !== 'ready') return
    setIsRunLoading(true)
    try {
      await fetch(`${API_BASE}/game/${gameId}/run`, { method: 'POST' })
      await fetchStatus()
    } catch (error) {
      console.error('Error running game:', error)
    } finally {
      setIsRunLoading(false)
    }
  }

  const pauseGame = async () => {
    if (!gameId) return
    try {
      await fetch(`${API_BASE}/game/${gameId}/pause`, { method: 'POST' })
    } catch (error) {
      console.error('Error pausing game:', error)
    }
  }

  const resumeGame = async () => {
    if (!gameId) return
    try {
      await fetch(`${API_BASE}/game/${gameId}/resume`, { method: 'POST' })
    } catch (error) {
      console.error('Error resuming game:', error)
    }
  }

  const runEvolution = useCallback(async (triggerGameId?: string) => {
    setIsEvolutionLoading(true)
    try {
      await fetch(`${API_BASE}/evolution/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          iterations: 1,
          train_games: 1,
          ab_games: 4,
          game_runner: 'mock',
          win_rate_threshold: 0,
          trigger_game_id: triggerGameId ?? null
        })
      })
      await fetchEvolutionStatus()
    } catch (error) {
      console.error('Error running evolution:', error)
      alert('启动自进化失败，请检查后端日志')
    }
    setIsEvolutionLoading(false)
  }, [fetchEvolutionStatus])

  const rollbackVersion = async (version: string) => {
    try {
      await fetch(`${API_BASE}/evolution/rollback/${version}`, { method: 'POST' })
      await fetchEvolutionStatus()
    } catch (error) {
      console.error('Error rolling back version:', error)
      alert('版本回滚失败，请检查后端日志')
    }
  }

  const fetchStatus = useCallback(async () => {
    if (!gameId) return
    try {
      const response = await fetch(`${API_BASE}/game/${gameId}/status`)
      const data = await response.json() as GameStatus
      setGameStatus(data)
    } catch (error) {
      console.error('Error fetching status:', error)
    }
  }, [gameId])

  const fetchLogs = useCallback(async () => {
    if (!gameId) return
    try {
      const response = await fetch(`${API_BASE}/game/${gameId}/logs`)
      const data = await response.json() as { logs: GameLog[] }
      setLogs(data.logs)
    } catch (error) {
      console.error('Error fetching logs:', error)
    }
  }, [gameId])

  useEffect(() => {
    if (!gameId) return
    const refresh = () => {
      void fetchStatus()
      void fetchLogs()
    }
    
    const initialRefresh = window.setTimeout(refresh, 0)
    const interval = window.setInterval(refresh, 2000)
    
    return () => {
      window.clearTimeout(initialRefresh)
      window.clearInterval(interval)
    }
  }, [gameId, fetchLogs, fetchStatus])

  useEffect(() => {
    const initialRefresh = window.setTimeout(() => {
      void fetchEvolutionStatus()
    }, 0)
    const interval = window.setInterval(() => {
      void fetchEvolutionStatus()
    }, 3000)
    return () => {
      window.clearTimeout(initialRefresh)
      window.clearInterval(interval)
    }
  }, [fetchEvolutionStatus])

  useEffect(() => {
    const shouldTriggerAutoEvolution = (
      autoEvolveAfterGame
      && gameId
      && gameStatus?.status === 'finished'
      && autoEvolutionTriggeredGameIdRef.current !== gameId
      && !evolutionStatus?.is_running
      && !isEvolutionLoading
    )

    if (!shouldTriggerAutoEvolution || !gameId) return

    autoEvolutionTriggeredGameIdRef.current = gameId
    void runEvolution(gameId)
  }, [
    autoEvolveAfterGame,
    evolutionStatus?.is_running,
    gameId,
    gameStatus?.status,
    isEvolutionLoading,
    runEvolution,
  ])

  const formatPercent = (value?: number) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return '—'
    return `${(value * 100).toFixed(1)}%`
  }

  const formatSignedPercent = (value?: number | null) => {
    if (typeof value !== 'number' || Number.isNaN(value)) return '—'
    return `${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
  }

  const visibleLogs = dedupeConsecutiveVisibleLogs(logs)
  const agentDecisionLogs = logs.filter((log) => log.type === 'agent_decision' && log.decision)
  const latestAgentDecisionLogs = agentDecisionLogs.slice(-5).reverse()
  const activeVersion = (
    evolutionStatus?.versions.find((version) => version.version === gameStatus?.strategy_version)
    ?? evolutionStatus?.current
  )
  const latestCandidate = evolutionStatus?.versions
    .slice()
    .reverse()
    .find((version) => version.status === 'candidate' || version.accepted === false)

  const getPlayerName = (playerId?: string | null) => (
    gameStatus?.players.find((player) => player.id === playerId)?.name ?? playerId ?? '未知目标'
  )

  const getDecisionName = (decisionType?: string) => {
    switch (decisionType) {
      case 'run': return '上警'
      case 'stay': return '留警下'
      case 'speech': return '发言'
      case 'retreat': return '退水'
      case 'not_retreat': return '不退水'
      case 'vote': return '投票'
      case 'kill': return '夜刀'
      case 'check': return '查验'
      case 'save': return '解药'
      case 'poison': return '毒药'
      case 'shoot': return '开枪'
      case 'skip': return '跳过'
      case 'bomb': return '自爆'
      default: return decisionType || '决策'
    }
  }

  const parseNameList = (value: string) => (
    value
      .split(',')
      .map((name) => name.trim())
      .filter(Boolean)
  )

  const parseSheriffCandidateGroups = (content?: string) => {
    if (!content) return null

    if (content.includes('无人上警')) {
      return { candidates: new Set<string>(), bench: new Set<string>() }
    }

    const [candidatePart, benchPart] = content.split('|').map((part) => part.trim())
    const candidatesText = candidatePart?.replace(/^上警玩家:\s*/, '') ?? ''
    const candidates = candidatesText && candidatesText !== '无'
      ? parseNameList(candidatesText)
      : []

    if (benchPart?.includes('全员上警')) {
      return { candidates: new Set(candidates), bench: new Set<string>() }
    }

    const benchText = benchPart?.replace(/^警下玩家:\s*/, '') ?? ''
    const bench = benchText && benchText !== '无'
      ? parseNameList(benchText)
      : []

    return { candidates: new Set(candidates), bench: new Set(bench) }
  }

  const getSheriffCandidateGroupsAfterDecision = (decisionLog: GameLog) => {
    const decisionIndex = logs.indexOf(decisionLog)
    const candidateLog = logs.find((log, index) => (
      index > decisionIndex && log.type === 'sheriff_candidates'
    ))
    return parseSheriffCandidateGroups(candidateLog?.content)
  }

  const getDecisionDisplay = (log: GameLog) => {
    const rawDecision = getDecisionName(log.decision?.decision_type)
    const isSheriffElectionIntent = log.decision?.decision_type === 'run' || log.decision?.decision_type === 'stay'
    if (!isSheriffElectionIntent) {
      return rawDecision
    }

    const playerName = getPlayerName(log.player_id)
    const sheriffGroups = getSheriffCandidateGroupsAfterDecision(log)
    if (!sheriffGroups) {
      return `模型意图：${rawDecision}`
    }

    const effectiveDecision = sheriffGroups.candidates.has(playerName)
      ? '上警'
      : sheriffGroups.bench.has(playerName)
        ? '留警下'
        : rawDecision

    if (effectiveDecision === rawDecision) {
      return `实际${effectiveDecision}`
    }

    return `实际${effectiveDecision}（模型意图：${rawDecision}）`
  }

  const getVersionStateName = (version?: VersionSummary | null) => {
    if (!version) return '未初始化'
    if (version.version === evolutionStatus?.current_version) return '当前上场'
    if (version.status === 'candidate') return '候选'
    if (version.accepted === false) return '未接受'
    if (version.accepted === true) return '已接受'
    return '历史版本'
  }

  const getLoopStageName = (stage?: string) => {
    switch (stage) {
      case 'queued': return '排队中'
      case 'starting': return '采样启动'
      case 'completed': return '本轮完成'
      case 'ab_validated': return '已完成 A/B'
      case 'version_ready': return '版本就绪'
      case 'not_initialized': return '未初始化'
      default: return stage || '待运行'
    }
  }

  const getDecisionBadges = (log: GameLog) => {
    const reasoning = log.decision?.reasoning ?? ''
    const badges: Array<{ label: string; tone: 'gold' | 'red' | 'blue' }> = []
    if (reasoning.includes('修正非预言家越权') || reasoning.includes('禁止退水改口')) {
      badges.push({ label: '规则修正', tone: 'gold' })
    }
    if (reasoning.includes('未被授权悍跳') || reasoning.includes('避免未授权')) {
      badges.push({ label: '身份边界', tone: 'blue' })
    }
    if (reasoning.includes('LLM调用失败')) {
      badges.push({ label: 'LLM 兜底', tone: 'red' })
    }
    return badges
  }

  const renderEvolutionPanel = (compact = false) => {
    const current = evolutionStatus?.current
    const training = current?.training_summary
    const latestVersions = evolutionStatus?.versions.slice(-4).reverse() ?? []
    if (current && !latestVersions.some((version) => version.version === current.version)) {
      latestVersions.unshift(current)
    }
    const rubricSummary = evolutionStatus?.rubric_summary
    const trainingHealth = rubricSummary?.training_health
    const badCaseSummary = rubricSummary?.bad_case_summary
    const runtimeHealth = evolutionStatus?.status === 'error'
      ? '异常'
      : trainingHealth?.has_runtime_issues
        ? '有失败样本'
        : evolutionStatus?.status === 'running'
          ? '运行中'
          : '正常'
    const lastIterationResult = evolutionStatus?.latest_result?.history?.slice(-1)[0]?.result
    const lastValidatedVersion = evolutionStatus?.versions
      .slice()
      .reverse()
      .find((version) => version.ab_result)
    const latestAbResult = lastIterationResult?.ab_result ?? rubricSummary?.latest_ab_result ?? lastValidatedVersion?.ab_result
    const latestAccepted = lastIterationResult?.accepted ?? rubricSummary?.current_promoted_by_ab ?? lastValidatedVersion?.accepted
    const latestImprovement = lastIterationResult?.improvement ?? lastValidatedVersion?.improvement
    const pipelinePhase = evolutionStatus?.active_run?.phase
    const abDisplay = latestAbResult
      ? `${latestAbResult.b_wins ?? 0}/${latestAbResult.successful_games ?? latestAbResult.total_games ?? 0} 胜`
      : '待验证'
    const badCaseTotal = (
      (badCaseSummary?.nonseer_claim_repairs ?? 0)
      + (badCaseSummary?.llm_fallbacks ?? 0)
      + (badCaseSummary?.unauthorized_werewolf_fake_seer_blocks ?? 0)
      + (badCaseSummary?.public_claim_consistency_repairs ?? 0)
    )

    const renderMetricCard = (label: string, value: string | number, hint: string) => (
      <div style={{
        background: 'rgba(0,0,0,0.18)',
        borderRadius: '8px',
        padding: '12px',
        minHeight: '104px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between'
      }}>
        <div>
          <div style={{ color: '#aaa', fontSize: '0.86rem', fontWeight: 700 }}>{label}</div>
          <div style={{ color: '#777', fontSize: '0.74rem', lineHeight: 1.35, marginTop: '4px' }}>{hint}</div>
        </div>
        <div style={{ fontSize: '1.35rem', fontWeight: 800, marginTop: '10px' }}>{value}</div>
      </div>
    )

    const renderPipelineStep = (
      label: string,
      detail: string,
      state: 'done' | 'active' | 'idle' | 'failed',
    ) => (
      <div style={{
        background: state === 'active' ? 'rgba(34,170,102,0.14)' : state === 'failed' ? 'rgba(255,68,68,0.12)' : 'rgba(0,0,0,0.16)',
        border: `1px solid ${state === 'active' ? 'rgba(34,170,102,0.36)' : state === 'failed' ? 'rgba(255,68,68,0.32)' : 'rgba(255,255,255,0.08)'}`,
        borderRadius: '8px',
        padding: '10px 12px',
        minHeight: '82px'
      }}>
        <div style={{
          color: state === 'active' ? '#8df0bd' : state === 'failed' ? '#ff9999' : '#ddd',
          fontWeight: 800,
          fontSize: '0.9rem',
          marginBottom: '5px'
        }}>
          {label}
        </div>
        <div style={{ color: '#888', fontSize: '0.76rem', lineHeight: 1.4 }}>
          {detail}
        </div>
      </div>
    )

    return (
      <div style={{
        background: 'rgba(255,255,255,0.05)',
        borderRadius: '8px',
        padding: compact ? '16px' : '24px',
        border: '1px solid rgba(255,255,255,0.12)',
        marginBottom: compact ? '20px' : '30px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', alignItems: 'center', flexWrap: 'wrap', marginBottom: '16px' }}>
          <div>
            <h3 style={{ marginBottom: '6px', color: '#fff' }}>自进化状态</h3>
            <div style={{ color: '#aaa', fontSize: '0.95rem' }}>
              当前用于新开局的策略版本：<strong style={{ color: '#ffd700' }}>{evolutionStatus?.current_version || '未初始化'}</strong>
              {current?.parent ? <span>，父版本：{current.parent}</span> : null}
            </div>
            <div style={{ color: '#777', fontSize: '0.82rem', marginTop: '4px' }}>
              这些是版本管理和离线评估口径，不是当前观战对局的实时表现分。
            </div>
          </div>
          <button
            onClick={() => void runEvolution()}
            disabled={isEvolutionLoading || evolutionStatus?.is_running}
            style={{
              padding: '10px 18px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '0.95rem',
              fontWeight: 700,
              cursor: isEvolutionLoading || evolutionStatus?.is_running ? 'not-allowed' : 'pointer',
              background: evolutionStatus?.is_running ? '#777' : 'linear-gradient(135deg, #22aa66 0%, #2288aa 100%)',
              color: 'white',
              opacity: isEvolutionLoading ? 0.7 : 1
            }}
          >
            {evolutionStatus?.is_running ? '离线进化运行中...' : isEvolutionLoading ? '启动中...' : '生成一个候选版本'}
          </button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', marginBottom: compact ? '12px' : '18px' }}>
          {renderMetricCard(
            '闭环进度',
            getLoopStageName(rubricSummary?.loop_stage),
            '对局采样、分析调参、A/B 验证、晋级/回滚的当前阶段'
          )}
          {renderMetricCard(
            'A/B 验证',
            abDisplay,
            latestAbResult
              ? `${latestAbResult.version_a ?? '旧版'} vs ${latestAbResult.version_b ?? '候选'}`
              : '候选不会在 A/B 前替换当前版本'
          )}
          {renderMetricCard(
            '版本回溯',
            `${rubricSummary?.rollback_version_count ?? 0} 个`,
            '除当前上场版本外，可从本地版本链回溯的策略档案'
          )}
          {renderMetricCard(
            '运行健康',
            runtimeHealth,
            `完成 ${trainingHealth?.completed ?? training?.completed ?? 0}，超时 ${trainingHealth?.timed_out ?? training?.timed_out ?? 0}，失败 ${trainingHealth?.failed ?? training?.failed ?? 0}`
          )}
        </div>

        <div style={{ marginBottom: compact ? '12px' : '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', flexWrap: 'wrap', marginBottom: '8px' }}>
            <div style={{ color: '#aaa', fontSize: '0.9rem', fontWeight: 700 }}>进化流水线</div>
            {latestAbResult && (
              <div style={{ color: latestAccepted ? '#8df0bd' : '#ffb0b0', fontSize: '0.84rem', fontWeight: 700 }}>
                最近验证：{latestAccepted ? '候选晋级' : '保留旧版'}，
                胜率变化 {formatSignedPercent(latestImprovement)}
              </div>
            )}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px' }}>
            {renderPipelineStep(
              '1. 对局采样',
              evolutionStatus?.active_run
                ? `${evolutionStatus.active_run.train_games ?? 1} 局训练样本，来源：${evolutionStatus.active_run.trigger_game_id ? '当前观战局 + 离线样本' : '离线样本'}`
                : '用最近对局日志和离线样本构造训练集',
              pipelinePhase === 'starting' || pipelinePhase === 'queued' ? 'active' : latestAbResult ? 'done' : 'idle'
            )}
            {renderPipelineStep(
              '2. 分析调参',
              '分析胜率、夜刀、查验、投票和常见失误，生成角色策略补丁',
              evolutionStatus?.is_running && pipelinePhase !== 'queued' ? 'active' : latestAbResult ? 'done' : 'idle'
            )}
            {renderPipelineStep(
              '3. A/B 验证',
              latestAbResult
                ? `${latestAbResult.version_a ?? '旧版'} ${latestAbResult.a_wins ?? 0} 胜 / ${latestAbResult.version_b ?? '候选'} ${latestAbResult.b_wins ?? 0} 胜，成功样本 ${latestAbResult.successful_games ?? 0}/${latestAbResult.total_games ?? 0}`
                : '候选必须和当前上场版本对战后才会决定是否晋级',
              evolutionStatus?.is_running ? 'active' : latestAbResult ? 'done' : 'idle'
            )}
            {renderPipelineStep(
              '4. 晋级或回滚',
              latestAbResult
                ? latestAccepted
                  ? `${latestAbResult.version_b ?? '候选'} 已成为新上场版本`
                  : `${latestAbResult.version_a ?? '旧版'} 继续作为上场版本，候选进入 rejected 档案`
                : 'A/B 未完成前不会替换当前上场版本',
              evolutionStatus?.status === 'error' ? 'failed' : latestAbResult ? 'done' : 'idle'
            )}
          </div>
        </div>

        {evolutionStatus?.error && (
          <div style={{ color: '#ff7777', marginBottom: '12px', fontSize: '0.9rem' }}>{evolutionStatus.error}</div>
        )}

        <div style={{ marginBottom: compact ? '12px' : '18px' }}>
          <div style={{ color: '#aaa', fontSize: '0.9rem', marginBottom: '8px', fontWeight: 700 }}>质量守卫与 bad case</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '8px' }}>
            {renderMetricCard('底牌越权修正', badCaseSummary?.nonseer_claim_repairs ?? 0, '非预言家报查验/跳预言家被拦回底牌边界')}
            {renderMetricCard('未授权悍跳拦截', badCaseSummary?.unauthorized_werewolf_fake_seer_blocks ?? 0, '非唯一悍跳狼试图冒充预言家时被改写')}
            {renderMetricCard('身份一致性修正', badCaseSummary?.public_claim_consistency_repairs ?? 0, '公开身份前后冲突、退水改口等被纠正')}
            {renderMetricCard('LLM 兜底', badCaseSummary?.llm_fallbacks ?? 0, `模型失败时使用可解释默认决策；总守卫 ${badCaseTotal}`)}
          </div>
        </div>

        {latestVersions.length > 0 && (
          <div style={{ marginTop: compact ? '4px' : 0 }}>
            <div style={{ color: '#aaa', fontSize: '0.9rem', marginBottom: '8px' }}>最近版本链</div>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {latestVersions.map((version) => (
                <div key={version.version} style={{
                  padding: '6px 10px',
                  borderRadius: '8px',
                  background: version.version === evolutionStatus?.current_version ? 'rgba(255,215,0,0.18)' : 'rgba(255,255,255,0.08)',
                  border: version.version === evolutionStatus?.current_version ? '1px solid rgba(255,215,0,0.45)' : '1px solid rgba(255,255,255,0.08)',
                  color: version.version === evolutionStatus?.current_version ? '#ffd700' : '#ddd',
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <span>
                    {version.version}{version.parent ? ` ← ${version.parent}` : ''}
                    {version.status ? <span style={{ color: '#888', marginLeft: '6px' }}>{getVersionStateName(version)}</span> : null}
                  </span>
                  {version.version !== evolutionStatus?.current_version && !evolutionStatus?.is_running && (
                    <button
                      onClick={() => void rollbackVersion(version.version)}
                      style={{
                        border: '1px solid rgba(255,255,255,0.16)',
                        background: 'rgba(255,255,255,0.06)',
                        color: '#ddd',
                        borderRadius: '6px',
                        padding: '3px 7px',
                        cursor: 'pointer',
                        fontSize: '0.76rem',
                        fontWeight: 700
                      }}
                    >
                      回溯上场
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    )
  }

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'werewolf': return '#ff4444'
      case 'seer': return '#4444ff'
      case 'witch': return '#9944ff'
      case 'hunter': return '#ff9944'
      case 'villager': return '#44ff44'
      default: return '#888'
    }
  }

  const getRoleName = (role: string) => {
    switch (role) {
      case 'werewolf': return '狼人'
      case 'seer': return '预言家'
      case 'witch': return '女巫'
      case 'hunter': return '猎人'
      case 'villager': return '村民'
      default: return role
    }
  }

  const getPhaseName = (phase: string) => {
    switch (phase) {
      case 'night': return '夜晚'
      case 'sheriff_election': return '警长竞选'
      case 'sheriff_speech': return '警上发言'
      case 'sheriff_retreat': return '退水阶段'
      case 'sheriff_vote': return '警长投票'
      case 'sheriff_pk': return 'PK发言'
      case 'day': return '白天'
      case 'voting': return '放逐投票'
      case 'defense': return '遗言'
      case 'game_over': return '游戏结束'
      default: return phase
    }
  }

  const leftPlayers = gameStatus?.players.slice(0, 6) ?? []
  const rightPlayers = gameStatus?.players.slice(6, 12) ?? []

  const renderPlayerCard = (player: Player) => (
    <div
      key={player.id}
      style={{
        background: 'rgba(255,255,255,0.055)',
        border: `2px solid ${getRoleColor(player.role)}`,
        borderRadius: '8px',
        padding: '14px',
        minHeight: '108px',
        textAlign: 'center',
        opacity: !player.is_alive ? 0.5 : 1,
        filter: !player.is_alive ? 'grayscale(0.5)' : 'none',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center'
      }}
    >
      <div style={{ fontSize: '1.05rem', fontWeight: 800, marginBottom: '8px', overflowWrap: 'anywhere' }}>
        {player.is_sheriff ? '👑 ' : ''}{player.name}
      </div>
      <div style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '6px', color: getRoleColor(player.role) }}>
        {getRoleName(player.role)}
      </div>
      <div style={{ fontSize: '0.82rem', color: '#aaa' }}>
        {player.is_alive ? '🟢 存活' : '🔴 死亡'}
      </div>
      {player.in_sheriff_election && player.is_alive && (
        <div style={{ fontSize: '0.78rem', color: '#ffd700', marginTop: '6px' }}>
          🏃 警上
        </div>
      )}
    </div>
  )

  const renderPlayerColumn = (players: Player[], title: string) => (
    <aside style={{
      background: 'rgba(255,255,255,0.035)',
      border: '1px solid rgba(255,255,255,0.1)',
      borderRadius: '8px',
      padding: '14px',
      minHeight: 0,
      overflowY: 'auto'
    }}>
      <h3 style={{ color: '#ccc', fontSize: '1rem', marginBottom: '12px' }}>{title}</h3>
      <div style={{ display: 'grid', gap: '10px' }}>
        {players.map(renderPlayerCard)}
      </div>
    </aside>
  )

  const renderWatchingEvolutionInsights = () => {
    const latestDecision = latestAgentDecisionLogs[0]
    const versionChanges = activeVersion?.changes?.slice(0, 4) ?? []

    return (
      <section style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(260px, 0.95fr) minmax(340px, 1.4fr)',
        gap: '16px',
        marginBottom: '20px'
      }}>
        <div style={{
          background: 'rgba(255,255,255,0.045)',
          border: '1px solid rgba(255,215,0,0.22)',
          borderRadius: '8px',
          padding: '16px',
          minHeight: '178px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'flex-start', marginBottom: '12px' }}>
            <div>
              <h3 style={{ color: '#fff', fontSize: '1rem', marginBottom: '6px' }}>本局 Agent 档案</h3>
              <div style={{ color: '#ffd700', fontWeight: 800, fontSize: '1.35rem' }}>
                {gameStatus?.strategy_version || '未加载策略'}
              </div>
            </div>
            <span style={{
              padding: '5px 9px',
              borderRadius: '8px',
              background: 'rgba(255,215,0,0.14)',
              border: '1px solid rgba(255,215,0,0.28)',
              color: '#ffe58a',
              fontSize: '0.8rem',
              fontWeight: 700,
              whiteSpace: 'nowrap'
            }}>
              {getVersionStateName(activeVersion)}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: '8px', marginBottom: '12px' }}>
            <div>
              <div style={{ color: '#888', fontSize: '0.76rem' }}>父版本</div>
              <div style={{ color: '#ddd', fontWeight: 700, overflowWrap: 'anywhere' }}>{activeVersion?.parent || '无'}</div>
            </div>
            <div>
              <div style={{ color: '#888', fontSize: '0.76rem' }}>狼人胜率</div>
              <div style={{ color: '#ddd', fontWeight: 700 }}>{formatPercent(activeVersion?.analysis_summary?.werewolf_win_rate ?? activeVersion?.win_rate?.werewolves)}</div>
            </div>
            <div>
              <div style={{ color: '#888', fontSize: '0.76rem' }}>训练局</div>
              <div style={{ color: '#ddd', fontWeight: 700 }}>{activeVersion?.training_summary?.completed ?? activeVersion?.test_games ?? 0}</div>
            </div>
          </div>

          {versionChanges.length > 0 ? (
            <div style={{ display: 'grid', gap: '6px' }}>
              {versionChanges.map((change, index) => (
                <div key={`${activeVersion?.version}-change-${index}`} style={{
                  color: '#cfcfcf',
                  fontSize: '0.86rem',
                  lineHeight: 1.45,
                  paddingLeft: '10px',
                  borderLeft: '2px solid rgba(255,215,0,0.35)'
                }}>
                  {change}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: '#888', fontSize: '0.9rem' }}>
              暂无该版本的策略变更记录。
            </div>
          )}

          {latestCandidate && latestCandidate.version !== activeVersion?.version && (
            <div style={{ marginTop: '12px', color: '#aaa', fontSize: '0.84rem' }}>
              最新候选：<strong style={{ color: '#9ee6ff' }}>{latestCandidate.version}</strong>
              {latestCandidate.parent ? <span>，来自 {latestCandidate.parent}</span> : null}
            </div>
          )}
        </div>

        <div style={{
          background: 'rgba(255,255,255,0.045)',
          border: '1px solid rgba(153,68,255,0.24)',
          borderRadius: '8px',
          padding: '16px',
          minHeight: '178px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ color: '#fff', fontSize: '1rem' }}>Agent 决策显微镜</h3>
            <span style={{ color: '#aaa', fontSize: '0.82rem' }}>
              已捕获 {agentDecisionLogs.length} 次内部决策
            </span>
          </div>

          {latestDecision ? (
            <div style={{ display: 'grid', gap: '10px' }}>
              {latestAgentDecisionLogs.map((log) => {
                const badges = getDecisionBadges(log)
                return (
                  <div key={`${log.timestamp}-${log.player_id}-${log.decision?.decision_type}`} style={{
                    background: 'rgba(0,0,0,0.18)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: '8px',
                    padding: '10px 12px'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', flexWrap: 'wrap', marginBottom: '6px' }}>
                      <strong style={{ color: '#e3d4ff' }}>
                        {getPlayerName(log.player_id)} · {getDecisionDisplay(log)}
                        {log.decision?.target_id ? ` -> ${getPlayerName(log.decision.target_id)}` : ''}
                      </strong>
                      <span style={{ color: '#777', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    {badges.length > 0 && (
                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '6px' }}>
                        {badges.map((badge) => (
                          <span key={badge.label} style={{
                            padding: '3px 7px',
                            borderRadius: '6px',
                            fontSize: '0.72rem',
                            fontWeight: 800,
                            color: badge.tone === 'red' ? '#ffb0b0' : badge.tone === 'blue' ? '#9ee6ff' : '#ffe58a',
                            background: badge.tone === 'red' ? 'rgba(255,68,68,0.12)' : badge.tone === 'blue' ? 'rgba(68,153,255,0.12)' : 'rgba(255,215,0,0.12)',
                            border: badge.tone === 'red' ? '1px solid rgba(255,68,68,0.28)' : badge.tone === 'blue' ? '1px solid rgba(68,153,255,0.28)' : '1px solid rgba(255,215,0,0.28)'
                          }}>
                            {badge.label}
                          </span>
                        ))}
                      </div>
                    )}
                    <div style={{ color: '#cfcfcf', fontSize: '0.88rem', lineHeight: 1.45 }}>
                      {log.decision?.reasoning || '该决策未返回结构化理由。'}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ color: '#888', fontSize: '0.92rem', lineHeight: 1.6 }}>
              游戏开始后，这里会展示每个 Agent 的行动类型、目标和 reasoning，让观众看到当前策略版本如何做判断。
            </div>
          )}
        </div>
      </section>
    )
  }

  if (!gameId) {
    return (
      <div style={{
        padding: '40px',
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
        minHeight: '100vh',
        color: 'white'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <h1 style={{ fontSize: '3rem', marginBottom: '10px', textShadow: '0 0 20px rgba(255,68,68,0.5)' }}>
            🐺 AI 狼人杀
          </h1>
          <p style={{ color: '#888', fontSize: '1.1rem' }}>自进化 Agent 观战系统</p>
        </div>
        
        <div style={{ maxWidth: '760px', margin: '0 auto' }}>
          {renderEvolutionPanel()}
          <div style={{
            background: 'rgba(255,255,255,0.05)',
            borderRadius: '16px',
            padding: '40px',
            border: '1px solid rgba(255,255,255,0.1)'
          }}>
            <h2 style={{ marginBottom: '30px', textAlign: 'center' }}>创建新游戏</h2>
            
            <div style={{ marginBottom: '30px' }}>
              <h3 style={{ color: '#aaa', marginBottom: '15px' }}>玩家列表</h3>
              {playerNames.map((name, index) => (
                <div key={index} style={{ marginBottom: '10px' }}>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => {
                      const newNames = [...playerNames]
                      newNames[index] = e.target.value
                      setPlayerNames(newNames)
                    }}
                    style={{
                      width: '100%',
                      padding: '12px 16px',
                      borderRadius: '8px',
                      border: '1px solid rgba(255,255,255,0.2)',
                      background: 'rgba(255,255,255,0.05)',
                      color: 'white',
                      fontSize: '1rem'
                    }}
                  />
                </div>
              ))}
            </div>

            <button
              onClick={startNewGame}
              disabled={isLoading}
              style={{
                width: '100%',
                padding: '14px 32px',
                borderRadius: '8px',
                border: 'none',
                fontSize: '1.1rem',
                fontWeight: 600,
                cursor: isLoading ? 'not-allowed' : 'pointer',
                background: 'linear-gradient(135deg, #4466ff 0%, #6644ff 100%)',
                color: 'white',
                opacity: isLoading ? 0.6 : 1
              }}
            >
              {isLoading ? '创建中...' : '创建游戏'}
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{
      padding: '40px',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)',
      minHeight: '100vh',
      color: 'white'
    }}>
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <h1 style={{ fontSize: '3rem', marginBottom: '10px', textShadow: '0 0 20px rgba(255,68,68,0.5)' }}>
          🐺 AI 狼人杀
        </h1>
        <p style={{ color: '#888', fontSize: '1.1rem' }}>自进化 Agent 观战系统</p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px', flexWrap: 'wrap', gap: '20px' }}>
        <h2 style={{ fontSize: '1.8rem' }}>游戏 #{gameId.slice(0, 8)}</h2>
        <div style={{ display: 'flex', gap: '12px' }}>
          <span style={{
            padding: '8px 16px',
            borderRadius: '20px',
            background: '#4466ff',
            fontSize: '0.9rem',
            fontWeight: 600
          }}>
            回合 {gameStatus?.current_round || 1}
          </span>
          <span style={{
            padding: '8px 16px',
            borderRadius: '20px',
            background: '#666',
            fontSize: '0.9rem',
            fontWeight: 600
          }}>
            {getPhaseName(gameStatus?.current_phase || 'night')}
          </span>
          <span style={{
            padding: '8px 16px',
            borderRadius: '20px',
            background: gameStatus?.status === 'running' ? '#22aa22' : gameStatus?.status === 'finished' ? '#2266ff' : gameStatus?.status === 'paused' ? '#ff9900' : '#888',
            fontSize: '0.9rem',
            fontWeight: 600
          }}>
            {gameStatus?.status === 'running' ? '运行中' : gameStatus?.status === 'finished' ? '已结束' : gameStatus?.status === 'paused' ? '已暂停' : gameStatus?.status || '加载中'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {gameStatus?.status === 'ready' && (
          <button
            onClick={runGame}
            disabled={isRunLoading}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '1rem',
              fontWeight: 600,
              cursor: isRunLoading ? 'not-allowed' : 'pointer',
              opacity: isRunLoading ? 0.65 : 1,
              background: isRunLoading ? 'rgba(255,255,255,0.18)' : 'linear-gradient(135deg, #4466ff 0%, #6644ff 100%)',
              color: 'white'
            }}
          >
            {isRunLoading ? '启动中' : '开始游戏'}
          </button>
        )}
        {gameStatus?.status === 'running' && !gameStatus?.is_paused && (
          <button
            onClick={pauseGame}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '1rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: 'linear-gradient(135deg, #ff9900 0%, #ff6600 100%)',
              color: 'white'
            }}
          >
            暂停游戏
          </button>
        )}
        {gameStatus?.status === 'paused' && (
          <button
            onClick={resumeGame}
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '1rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: 'linear-gradient(135deg, #22aa22 0%, #228822 100%)',
              color: 'white'
            }}
          >
            继续游戏
          </button>
        )}
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 14px',
          borderRadius: '8px',
          background: autoEvolveAfterGame ? 'rgba(34,170,102,0.14)' : 'rgba(255,255,255,0.06)',
          border: autoEvolveAfterGame ? '1px solid rgba(34,170,102,0.36)' : '1px solid rgba(255,255,255,0.12)',
          color: '#ddd',
          cursor: 'pointer',
          userSelect: 'none'
        }}>
          <input
            type="checkbox"
            checked={autoEvolveAfterGame}
            onChange={(event) => setAutoEvolveAfterGame(event.target.checked)}
          />
          <span style={{ fontSize: '0.92rem', fontWeight: 700 }}>本局结束后自动进化</span>
        </label>
      </div>

      {renderEvolutionPanel(true)}

      {renderWatchingEvolutionInsights()}

      {gameStatus?.error && (
        <div style={{
          textAlign: 'center',
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(255,0,0,0.2) 0%, rgba(255,68,68,0.2) 100%)',
          border: '2px solid #ff4444',
          borderRadius: '12px',
          marginBottom: '30px',
          fontSize: '1.2rem',
          fontWeight: 700,
          color: '#ff4444'
        }}>
          ❌ 错误: {gameStatus.error}
        </div>
      )}

      {gameStatus?.winner && (
        <div style={{
          textAlign: 'center',
          padding: '24px',
          background: 'linear-gradient(135deg, rgba(255,215,0,0.2) 0%, rgba(255,165,0,0.2) 100%)',
          border: '2px solid #ffd700',
          borderRadius: '12px',
          marginBottom: '30px',
          fontSize: '1.5rem',
          fontWeight: 700,
          color: '#ffd700'
        }}>
          🎉 {gameStatus.winner === 'werewolves' ? '狼人' : '好人'}获胜！
        </div>
      )}

      {!gameStatus ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#aaa' }}>
          加载中...
        </div>
      ) : (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(170px, 220px) minmax(420px, 1fr) minmax(170px, 220px)',
            gap: '18px',
            height: 'calc(100vh - 360px)',
            minHeight: '560px',
            marginBottom: '20px'
          }}>
            {renderPlayerColumn(leftPlayers, '玩家 1-6')}

          <main style={{
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '8px',
            padding: '20px',
            border: '1px solid rgba(255,255,255,0.1)',
            minHeight: 0,
            overflowY: 'auto'
          }}>
            <h3 style={{ marginBottom: '20px', color: '#ccc' }}>📜 游戏日志</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {visibleLogs.map((log, index) => {
                return (
                <div key={index} style={{
                  padding: '10px 14px',
                  borderRadius: '6px',
                  background: log.type === 'game_start' || log.type === 'game_end' ? 'rgba(68,102,255,0.2)' :
                          log.type === 'phase_change' ? 'rgba(68,255,68,0.15)' :
                          log.type === 'speech' ? 'rgba(255,153,68,0.15)' :
                          log.type === 'sheriff_speech' ? 'rgba(255,153,68,0.15)' :
                          log.type === 'pk_speech' ? 'rgba(255,153,68,0.15)' :
                          log.type === 'last_words' ? 'rgba(128,0,128,0.2)' :
                          log.type === 'night_action' ? 'rgba(255,68,68,0.15)' :
                          log.type === 'death' ? 'rgba(255,0,0,0.2)' :
                          log.type === 'vote' ? 'rgba(255,153,68,0.15)' :
                          log.type === 'sheriff_vote' ? 'rgba(100,149,237,0.2)' :
                          log.type === 'vote_count' ? 'rgba(255,215,0,0.2)' :
                          log.type === 'sheriff_vote_result' ? 'rgba(255,215,0,0.2)' :
                          log.type === 'agent_decision' ? 'rgba(153,68,255,0.15)' :
                          log.type === 'sheriff_candidates' ? 'rgba(100,149,237,0.2)' :
                          log.type === 'sheriff_retreat' ? 'rgba(200,200,200,0.2)' :
                          log.type === 'sheriff_elected' ? 'rgba(255,215,0,0.25)' :
                          log.type === 'sheriff_lost' ? 'rgba(128,128,128,0.2)' :
                          log.type === 'speak_direction' ? 'rgba(138,43,226,0.2)' :
                          log.type === 'vote_result' ? 'rgba(255,165,0,0.2)' :
                          'rgba(255,255,255,0.03)',
                  fontSize: '0.95rem',
                  lineHeight: 1.5,
                  borderLeft: log.type === 'game_start' || log.type === 'game_end' ? '4px solid #4466ff' :
                              log.type === 'phase_change' ? '4px solid #44ff44' :
                              log.type === 'speech' ? '4px solid #ff9944' :
                              log.type === 'sheriff_speech' ? '4px solid #ff9944' :
                              log.type === 'pk_speech' ? '4px solid #ff9944' :
                              log.type === 'last_words' ? '4px solid #800080' :
                              log.type === 'night_action' ? '4px solid #ff4444' :
                              log.type === 'death' ? '4px solid #ff0000' :
                              log.type === 'vote' ? '4px solid #ff9944' :
                              log.type === 'sheriff_vote' ? '4px solid #6495ed' :
                              log.type === 'vote_count' ? '4px solid #ffd700' :
                              log.type === 'sheriff_vote_result' ? '4px solid #ffd700' :
                              log.type === 'agent_decision' ? '4px solid #9944ff' :
                              log.type === 'sheriff_candidates' ? '4px solid #6495ed' :
                              log.type === 'sheriff_retreat' ? '4px solid #c8c8c8' :
                              log.type === 'sheriff_elected' ? '4px solid #ffd700' :
                              log.type === 'sheriff_lost' ? '4px solid #808080' :
                              log.type === 'speak_direction' ? '4px solid #8a2be2' :
                              log.type === 'vote_result' ? '4px solid #ffa500' :
                              '4px solid #4466ff'
                }}>
                  <span style={{ color: '#888', marginRight: '10px', fontFamily: 'monospace' }}>
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span style={{ color: '#aaa', marginRight: '10px', fontWeight: 600 }}>
                    [{log.type === 'game_start' ? '开始' :
                      log.type === 'phase_change' ? '阶段' :
                      log.type === 'speech' ? '发言' :
                      log.type === 'sheriff_speech' ? '警上发言' :
                      log.type === 'pk_speech' ? 'PK发言' :
                      log.type === 'last_words' ? '遗言' :
                      log.type === 'night_action' ? '夜动' :
                      log.type === 'death' ? '死亡' :
                      log.type === 'vote' ? '投票' :
                      log.type === 'sheriff_vote' ? '警长票' :
                      log.type === 'vote_count' ? '计票' :
                      log.type === 'sheriff_vote_result' ? '警计票' :
                      log.type === 'game_end' ? '结束' :
                      log.type === 'agent_decision' ? '决策' :
                      log.type === 'sheriff_candidates' ? '警长竞选' :
                      log.type === 'sheriff_retreat' ? '退水' :
                      log.type === 'sheriff_elected' ? '警长当选' :
                      log.type === 'sheriff_lost' ? '警徽流失' :
                      log.type === 'speak_direction' ? '发言方向' :
                      log.type === 'vote_result' ? '投票结果' :
                      log.type}]
                  </span>
                  <span style={{ color: '#ddd' }}>
                    {log.type === 'game_start' && '游戏开始'}
                    {log.type === 'phase_change' && `第${log.round_number}回合 - ${getPhaseName(log.phase ?? '')}`}
                    {log.type === 'game_end' && `游戏结束 - ${log.winner === 'werewolves' ? '狼人' : '好人'}获胜`}
                    {log.type === 'death' && `${log.player_name || gameStatus?.players?.find((p) => p.id === log.player_id)?.name} 死亡 (${log.cause})`}
                    {log.type === 'night_action' && `${gameStatus?.players?.find((p) => p.id === log.action?.actor)?.name} ${log.action?.action === 'kill' ? '刀' : log.action?.action === 'check' ? '查验' : log.action?.action === 'save' ? '救' : log.action?.action === 'poison' ? '毒' : log.action?.action} ${gameStatus?.players?.find((p) => p.id === log.action?.target)?.name}${log.action?.result ? ` (结果: ${log.action.result === 'werewolf' ? '狼人' : '好人'})` : ''}`}
                    {log.type === 'vote' && `${gameStatus?.players?.find((p) => p.id === log.vote?.voter)?.name} 投给 ${gameStatus?.players?.find((p) => p.id === log.vote?.target)?.name}`}
                    {log.type === 'speech' && (
                      <div>
                        <strong>{log.player_name || gameStatus?.players?.find((p) => p.id === log.player_id)?.name} 发言:</strong>
                        <div style={{ marginTop: '4px', fontSize: '0.95rem', opacity: 0.9 }}>
                          {log.content}
                        </div>
                      </div>
                    )}
                    {log.type === 'sheriff_speech' && (
                      <div>
                        <strong>{log.player_name || gameStatus?.players?.find((p) => p.id === log.player_id)?.name} 警上发言:</strong>
                        <div style={{ marginTop: '4px', fontSize: '0.95rem', opacity: 0.9 }}>
                          {log.content}
                        </div>
                      </div>
                    )}
                    {log.type === 'pk_speech' && (
                      <div>
                        <strong>{log.player_name || gameStatus?.players?.find((p) => p.id === log.player_id)?.name} PK发言:</strong>
                        <div style={{ marginTop: '4px', fontSize: '0.95rem', opacity: 0.9 }}>
                          {log.content}
                        </div>
                      </div>
                    )}
                    {log.type === 'last_words' && (
                      <div>
                        <strong>{log.player_name || gameStatus?.players?.find((p) => p.id === log.player_id)?.name} 遗言:</strong>
                        <div style={{ marginTop: '4px', fontSize: '0.95rem', opacity: 0.9 }}>
                          {log.content}
                        </div>
                      </div>
                    )}
                    {log.type === 'sheriff_vote' && log.content}
                    {log.type === 'vote_count' && log.content}
                    {log.type === 'sheriff_vote_result' && log.content}
                    {log.type === 'sheriff_candidates' && log.content}
                    {log.type === 'sheriff_retreat' && log.content}
                    {log.type === 'sheriff_elected' && log.content}
                    {log.type === 'sheriff_lost' && log.content}
                    {log.type === 'speak_direction' && log.content}
                    {log.type === 'vote_result' && log.content}
                  </span>
                </div>
                )
              })}
            </div>
          </main>

            {renderPlayerColumn(rightPlayers, '玩家 7-12')}
          </div>
        </>
      )}

      <button
        onClick={() => {
          setGameId(null)
          setGameStatus(null)
          setLogs([])
        }}
        style={{
          marginTop: '20px',
          padding: '14px 32px',
          borderRadius: '8px',
          border: 'none',
          fontSize: '1.1rem',
          fontWeight: 600,
          cursor: 'pointer',
          background: 'rgba(255,255,255,0.1)',
          color: 'white'
        }}
      >
        返回主页
      </button>
    </div>
  )
}

export default App
