'use client'

import { useMemo } from 'react'
import {
  Background,
  Controls,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { KnowledgeMapData } from '@/lib/api/virtual-classroom'

interface KnowledgeMapFlowProps {
  data: KnowledgeMapData | null
}

const STAGE_WIDTH = 380
const STAGE_GAP = 240

export default function KnowledgeMapFlow({ data }: KnowledgeMapFlowProps) {
  const { nodes, edges } = useMemo(() => {
    if (!data?.stages?.length) {
      return { nodes: [], edges: [] }
    }

    const nodeList: Node[] = []
    const edgeList: Edge[] = []

    if (data.storyline) {
      nodeList.push({
        id: 'storyline',
        position: { x: 0, y: -220 },
        data: {
          label: (
            <div className="max-w-md">
              <p className="text-sm leading-relaxed">{data.storyline}</p>
            </div>
          ),
        },
        style: {
          width: 520,
          borderRadius: 12,
          border: '1px solid hsl(var(--border))',
          background: 'hsl(var(--card))',
          padding: 12,
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
        },
      })
    }

    data.stages.forEach((stage, index) => {
      const id = stage.id || `stage-${index + 1}`
      const y = index * STAGE_GAP

      nodeList.push({
        id,
        position: { x: 0, y },
        data: {
          label: (
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">
                  {index + 1}
                </span>
                <span className="font-medium leading-tight">{stage.label}</span>
              </div>
              {stage.summary && (
                <p className="text-sm text-muted-foreground">{stage.summary}</p>
              )}
              {stage.concepts && stage.concepts.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-1">
                  {stage.concepts.map((concept, conceptIndex) => (
                    <span
                      key={`${id}-concept-${conceptIndex}`}
                      className="rounded-full bg-muted px-2 py-0.5 text-xs"
                    >
                      {concept.label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ),
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
        style: {
          width: STAGE_WIDTH,
          borderRadius: 12,
          border: '1px solid hsl(var(--border))',
          background: 'hsl(var(--card))',
          padding: 12,
          boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
        },
      })

      if (index > 0) {
        const previousId = data.stages?.[index - 1]?.id || `stage-${index}`
        edgeList.push({
          id: `${previousId}-${id}`,
          source: previousId,
          target: id,
          type: 'smoothstep',
          label: stage.bridgeToNext || '→',
          labelStyle: { fontSize: 11, fill: 'hsl(var(--muted-foreground))' },
          labelBgStyle: { fill: 'hsl(var(--background))', fillOpacity: 0.85 },
          markerEnd: { type: MarkerType.ArrowClosed },
          style: { stroke: 'hsl(var(--muted-foreground))', strokeWidth: 1.5 },
        })
      }
    })

    return { nodes: nodeList, edges: edgeList }
  }, [data])

  if (!data?.stages?.length) {
    return null
  }

  return (
    <div className="h-[600px] w-full overflow-hidden rounded-md border">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        nodesConnectable={false}
        nodesDraggable
        minZoom={0.2}
        maxZoom={1.5}
      >
        <Background gap={20} size={1} />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  )
}
