"use client"

import {
  type Edge,
  type Node,
  type ReactFlowInstance,
  useOnSelectionChange,
  useReactFlow,
} from "@xyflow/react"
import React, {
  createContext,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react"
import type {
  NodeType,
  WorkflowCanvasRef,
} from "@/components/builder/canvas/canvas"
import type { EventsSidebarRef } from "@/components/builder/events/events-sidebar"
import type { ActionPanelRef } from "@/components/builder/panel/action-panel"
import { pruneReactFlowInstance } from "@/lib/workflow"
import { useWorkflow } from "@/providers/workflow"

interface ReactFlowContextType {
  reactFlow: ReactFlowInstance
  workflowId: string | null
  workspaceId: string
  selectedNodeId: string | null
  getNode: (id: string) => Node | undefined
  setNodes: React.Dispatch<SetStateAction<Node[]>>
  setEdges: React.Dispatch<SetStateAction<Edge[]>>
  setSelectedNodeId: React.Dispatch<SetStateAction<string | null>>
  canvasRef: React.RefObject<WorkflowCanvasRef>
  sidebarRef: React.RefObject<EventsSidebarRef>
  actionPanelRef: React.RefObject<ActionPanelRef>
  isSidebarCollapsed: boolean
  isActionPanelCollapsed: boolean
  toggleSidebar: () => void
  toggleActionPanel: () => void
  expandSidebarAndFocusEvents: () => void
  selectedActionEventRef?: string
  setSelectedActionEventRef: React.Dispatch<SetStateAction<string | undefined>>
  currentExecutionId: string | null
  setCurrentExecutionId: React.Dispatch<SetStateAction<string | null>>
}

const ReactFlowInteractionsContext = createContext<
  ReactFlowContextType | undefined
>(undefined)

interface ReactFlowInteractionsProviderProps {
  children: ReactNode
}

export const WorkflowBuilderProvider: React.FC<
  ReactFlowInteractionsProviderProps
> = ({ children }) => {
  const reactFlowInstance = useReactFlow()
  const { workspaceId, workflowId, error, updateWorkflow } = useWorkflow()

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [selectedActionEventRef, setSelectedActionEventRef] = useState<
    string | undefined
  >(undefined)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(false)
  const [isActionPanelCollapsed, setIsActionPanelCollapsed] =
    React.useState(false)
  const [currentExecutionId, setCurrentExecutionId] = useState<string | null>(
    null
  )
  const canvasRef = useRef<WorkflowCanvasRef>(null)
  const sidebarRef = useRef<EventsSidebarRef>(null)
  const actionPanelRef = useRef<ActionPanelRef>(null)

  useEffect(() => {
    setSelectedNodeId(null)
    setCurrentExecutionId(null)
  }, [workflowId])

  const setReactFlowNodes = useCallback(
    (nodes: Node[] | ((nodes: Node[]) => Node[])) => {
      reactFlowInstance.setNodes(nodes)
      updateWorkflow({ object: pruneReactFlowInstance(reactFlowInstance) })
    },
    [workflowId, reactFlowInstance]
  )
  const setReactFlowEdges = useCallback(
    (edges: Edge[] | ((edges: Edge[]) => Edge[])) => {
      reactFlowInstance.setEdges(edges)
      updateWorkflow({ object: pruneReactFlowInstance(reactFlowInstance) })
    },
    [workflowId, reactFlowInstance]
  )
  useOnSelectionChange({
    onChange: ({ nodes }: { nodes: NodeType[] }) => {
      const nodeSelected = nodes[0]
      if (nodeSelected?.type === "selector") {
        return
      }
      setSelectedNodeId(nodeSelected?.id ?? null)
    },
  })

  const toggleSidebar = React.useCallback(() => {
    setIsSidebarCollapsed((prev: boolean) => {
      const newState = !prev
      if (sidebarRef.current) {
        if (newState) {
          sidebarRef.current.collapse()
        } else {
          sidebarRef.current.expand()
        }
      }
      return newState
    })
  }, [sidebarRef])

  const toggleActionPanel = React.useCallback(() => {
    setIsActionPanelCollapsed((prev: boolean) => {
      const newState = !prev
      if (actionPanelRef.current) {
        if (newState) {
          actionPanelRef.current.collapse()
        } else {
          actionPanelRef.current.expand()
        }
      }
      return newState
    })
  }, [actionPanelRef])

  const expandSidebarAndFocusEvents = React.useCallback(() => {
    setIsSidebarCollapsed(() => {
      const newState = false
      if (sidebarRef.current) {
        sidebarRef.current.expand()
        // sidebarRef.current.setActiveTab("workflow-events")
      }
      return newState
    })
  }, [sidebarRef])

  const value = React.useMemo(
    () => ({
      workflowId,
      workspaceId,
      selectedNodeId,
      selectedActionEventRef,
      getNode: reactFlowInstance.getNode,
      setNodes: setReactFlowNodes,
      setEdges: setReactFlowEdges,
      setSelectedNodeId,
      setSelectedActionEventRef,
      reactFlow: reactFlowInstance,
      canvasRef,
      sidebarRef,
      isSidebarCollapsed,
      toggleSidebar,
      expandSidebarAndFocusEvents,
      actionPanelRef,
      isActionPanelCollapsed,
      toggleActionPanel,
      currentExecutionId,
      setCurrentExecutionId,
    }),
    [
      workflowId,
      workspaceId,
      selectedNodeId,
      reactFlowInstance,
      setReactFlowNodes,
      setReactFlowEdges,
      setSelectedNodeId,
      selectedActionEventRef,
      setSelectedActionEventRef,
      canvasRef,
      sidebarRef,
      isSidebarCollapsed,
      toggleSidebar,
      expandSidebarAndFocusEvents,
      actionPanelRef,
      isActionPanelCollapsed,
      toggleActionPanel,
      currentExecutionId,
      setCurrentExecutionId,
    ]
  )

  // Don't render anything if no workflow is selected
  if (!workflowId) {
    return children
  }
  if (error) {
    console.error("Builder: Error fetching workflow metadata:", error)
    throw error
  }

  return (
    <ReactFlowInteractionsContext.Provider value={value}>
      {children}
    </ReactFlowInteractionsContext.Provider>
  )
}

export const useWorkflowBuilder = (): ReactFlowContextType => {
  const context = useContext(ReactFlowInteractionsContext)
  if (context === undefined) {
    throw new Error(
      "useReactFlowInteractions must be used within a ReactFlowInteractionsProvider"
    )
  }
  return context
}
