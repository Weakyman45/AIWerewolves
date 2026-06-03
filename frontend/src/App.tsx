import { useState, useEffect, useRef, useCallback } from 'react'

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
}

type StartGameResponse = {
  game_id: string
}

function App() {
  const [gameId, setGameId] = useState<string | null>(null)
  const [gameStatus, setGameStatus] = useState<GameStatus | null>(null)
  const [logs, setLogs] = useState<GameLog[]>([])
  const [playerNames, setPlayerNames] = useState<string[]>(defaultPlayerNames)
  const [isLoading, setIsLoading] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (gameStatus?.status !== 'finished') {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, gameStatus])

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
    } catch (error) {
      console.error('Error starting game:', error)
      alert('创建游戏失败，请检查后端是否启动')
    }
    setIsLoading(false)
  }

  const runGame = async () => {
    if (!gameId) return
    try {
      await fetch(`${API_BASE}/game/${gameId}/run`, { method: 'POST' })
    } catch (error) {
      console.error('Error running game:', error)
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
        
        <div style={{ maxWidth: '600px', margin: '0 auto' }}>
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
            style={{
              padding: '10px 24px',
              borderRadius: '8px',
              border: 'none',
              fontSize: '1rem',
              fontWeight: 600,
              cursor: 'pointer',
              background: 'linear-gradient(135deg, #4466ff 0%, #6644ff 100%)',
              color: 'white'
            }}
          >
            开始游戏
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
      </div>

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
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '20px',
            marginBottom: '40px'
          }}>
            {gameStatus.players.map((player) => (
              <div
                key={player.id}
                style={{
                  background: 'rgba(255,255,255,0.05)',
                  border: `3px solid ${getRoleColor(player.role)}`,
                  borderRadius: '12px',
                  padding: '24px',
                  textAlign: 'center',
                  opacity: !player.is_alive ? 0.5 : 1,
                  filter: !player.is_alive ? 'grayscale(0.5)' : 'none'
                }}
              >
                <div style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '12px' }}>
                  {player.is_sheriff ? '👑 ' : ''}{player.name}
                </div>
                <div style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '8px', color: getRoleColor(player.role) }}>
                  {getRoleName(player.role)}
                </div>
                <div style={{ fontSize: '0.95rem', color: '#aaa' }}>
                  {player.is_alive ? '🟢 存活' : '🔴 死亡'}
                </div>
                {player.in_sheriff_election && player.is_alive && (
                  <div style={{ fontSize: '0.85rem', color: '#ffd700', marginTop: '8px' }}>
                    🏃 警上
                  </div>
                )}
              </div>
            ))}
          </div>

          <div style={{
            background: 'rgba(255,255,255,0.03)',
            borderRadius: '12px',
            padding: '24px',
            border: '1px solid rgba(255,255,255,0.1)',
            maxHeight: '700px',
            overflowY: 'auto'
          }}>
            <h3 style={{ marginBottom: '20px', color: '#ccc' }}>📜 游戏日志</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {logs.map((log, index) => {
                // 隐藏决策日志
                if (log.type === 'agent_decision') {
                  return null;
                }
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
              <div ref={logsEndRef} />
            </div>
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
