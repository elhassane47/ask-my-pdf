import streamlit as st
import uuid
import time
import json
from typing import TypedDict, Optional, Dict, Any, List
from dataclasses import dataclass
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_community.chat_models import ChatOllama

# Configuration de la page Streamlit
st.set_page_config(
    page_title="🤖 Assistant IA avec Interruptions LangGraph",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour améliorer l'interface
st.markdown("""
<style>
    .interrupt-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
    }
    .status-success {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .status-waiting {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .status-error {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
    }
    .event-message {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .event-header {
        font-weight: bold;
        font-size: 1.1em;
        margin-bottom: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .event-content {
        line-height: 1.6;
    }
    .event-metadata {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 5px;
        padding: 10px;
        margin-top: 10px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Définition de l'état du graphe
class WorkflowState(TypedDict):
    user_request: str
    analysis: str
    generated_content: str
    human_feedback: str
    final_result: str
    step: str
    metadata: Dict[str, Any]
    events: List[Dict[str, Any]]
    use_llm: bool
    llm_decision_made: bool

def dispatch_event(event_type: str, content: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """Dispatch un événement personnalisé"""
    return {
        "type": event_type,
        "data": {
            "content": content,
            "timestamp": time.time(),
            "metadata": metadata or {}
        }
    }

def update_workflow_events(events: List[Dict[str, Any]]):
    """Met à jour les événements du workflow dans l'état de session"""
    if 'events' not in st.session_state.workflow_state:
        st.session_state.workflow_state['events'] = []
    
    # Add new events that aren't already present
    for event in events:
        event_id = f"{event['type']}_{event['data']['timestamp']}"
        existing_events = st.session_state.workflow_state['events']
        
        if not any(f"{e['type']}_{e['data']['timestamp']}" == event_id for e in existing_events):
            st.session_state.workflow_state['events'].append(event)

def process_workflow_events(events: List[Dict[str, Any]]):
    """Traite et affiche les événements du workflow en temps réel"""
    for event in events:
        # Add event to messages if not already present
        event_id = f"{event['type']}_{event['data']['timestamp']}"
        existing_events = [msg for msg in st.session_state.messages if msg.get('type') == 'event']
        
        if not any(f"{msg['event_type']}_{msg['timestamp']}" == event_id for msg in existing_events):
            st.session_state.messages.append({
                'type': 'event',
                'event_type': event['type'],
                'content': event['data']['content'],
                'timestamp': event['data']['timestamp'],
                'metadata': event['data'].get('metadata', {})
            })
            
            # Force a rerun to show the event immediately
            st.rerun()

# Initialisation de l'état Streamlit
def init_session_state():
    """Initialise l'état de la session Streamlit"""
    if 'workflow_state' not in st.session_state:
        st.session_state.workflow_state = {
            'current_thread_id': None,
            'interrupted': False,
            'interrupt_data': None,
            'workflow_completed': False,
            'execution_history': [],
            'current_step': 'idle',
            'events': [],
            'use_llm': True, # Default to True
            'llm_decision_made': False # Default to False
        }
    
    if 'graph' not in st.session_state:
        st.session_state.graph = None
    
    if 'messages' not in st.session_state:
        st.session_state.messages = []

# Configuration du modèle LLM
@st.cache_resource
def get_llm():
    """Initialise le modèle LLM via LM Studio (Llama-3.2-3b-instruct)"""
    try:
        # Utilise LM Studio local avec le modèle llama-3.2-3b-instruct
        return ChatOllama(
            model="llama-3.2-3b-instruct",
            temperature=0.7,
            base_url="http://localhost:1234"  # Change if your LM Studio runs on a different port
        )
    except Exception as e:
        st.error(f"Erreur d'initialisation LLM: {e}")
        return None

# Nœuds du workflow LangGraph
def analyze_request_node(state: WorkflowState) -> WorkflowState:
    """Analyse la demande utilisateur"""
    print(f"🔍 Analyse de la demande: {state['user_request']}")
    
    # Simulation d'analyse (vous pouvez utiliser un vrai LLM ici)
    request = state['user_request'].lower()
    
    if any(word in request for word in ['résumé', 'summary', 'synthèse']):
        analysis = "Demande de génération de résumé détectée"
        content_type = "summary"
    elif any(word in request for word in ['email', 'mail', 'message']):
        analysis = "Demande de rédaction d'email détectée"
        content_type = "email"
    elif any(word in request for word in ['code', 'script', 'programme']):
        analysis = "Demande de génération de code détectée"
        content_type = "code"
    else:
        analysis = "Demande générale de contenu détectée"
        content_type = "general"
    
    # Dispatch custom event
    analysis_event = dispatch_event(
        "analysis_completed",
        f"🔍 **Analyse terminée**\n\n**Type de contenu détecté:** {content_type}\n**Analyse:** {analysis}",
        {"content_type": content_type, "analysis": analysis}
    )
    
    # Add event to state
    events = state.get("events", [])
    events.append(analysis_event)
    
    return {
        **state,
        "analysis": analysis,
        "step": "analyzed",
        "metadata": {**state.get("metadata", {}), "content_type": content_type},
        "events": events
    }

def llm_decision_node(state: WorkflowState) -> WorkflowState:
    """Nœud d'interruption pour décision d'utilisation du LLM"""
    print("🤖 Demande de décision pour l'utilisation du LLM...")
    
    # Dispatch custom event for LLM decision request
    llm_decision_event = dispatch_event(
        "llm_decision_requested",
        f"🤖 **Décision LLM requise**\n\n**Demande:** {state['user_request']}\n**Type de contenu:** {state['metadata'].get('content_type', 'general')}\n\nVoulez-vous utiliser l'IA pour générer le contenu ?",
        {"content_type": state["metadata"].get("content_type", "general")}
    )
    
    # Add event to state
    events = state.get("events", [])
    events.append(llm_decision_event)
    
    # Créer les données d'interruption pour la décision LLM
    interrupt_payload = {
        "task": "Décidez si vous voulez utiliser l'IA pour générer le contenu",
        "user_request": state["user_request"],
        "analysis": state["analysis"],
        "content_type": state["metadata"].get("content_type", "general"),
        "interruption_type": "llm_decision",
        "timestamp": time.time()
    }
    
    # INTERRUPTION : Le workflow s'arrête ici et attend la décision de l'utilisateur
    result = interrupt(interrupt_payload)
    
    # Cette ligne ne s'exécute qu'après la reprise avec Command(resume=...)
    use_llm = result.get("use_llm", True)
    
    # Dispatch event for decision made
    decision_event = dispatch_event(
        "llm_decision_made",
        f"✅ **Décision LLM prise**\n\n**Utilisation de l'IA:** {'Oui' if use_llm else 'Non'}",
        {"use_llm": use_llm, "content_type": state["metadata"].get("content_type", "general")}
    )
    
    events.append(decision_event)
    
    return {
        **state,
        "use_llm": use_llm,
        "llm_decision_made": True,
        "step": "llm_decided",
        "events": events
    }

def generate_content_node(state: WorkflowState) -> WorkflowState:
    """Génère le contenu initial avec ou sans l'IA"""
    print(f"🤖 Génération de contenu pour: {state['analysis']}")
    
    content_type = state["metadata"].get("content_type", "general")
    use_llm = state.get("use_llm", True)
    
    try:
        if use_llm:
            # Utiliser le LLM pour générer le contenu
            llm = get_llm()
            
            # Templates de prompts selon le type de contenu
            prompts = {
                "summary": f"Crée un résumé professionnel sur le sujet suivant: {state['user_request']}",
                "email": f"Rédige un email professionnel concernant: {state['user_request']}",
                "code": f"Génère du code Python pour: {state['user_request']}",
                "general": f"Crée du contenu pertinent pour: {state['user_request']}"
            }
            
            prompt = prompts.get(content_type, prompts["general"])
            
            if llm:
                response = llm.invoke([HumanMessage(content=prompt)])
                generated_content = response.content
            else:
                # Contenu de fallback si LLM indisponible
                generated_content = f"Contenu généré pour: {state['user_request']}\n\nCeci est un exemple de contenu qui serait normalement généré par l'IA. Vous pouvez l'éditer selon vos besoins."
        else:
            # Générer du contenu sans LLM (template-based)
            templates = {
                "summary": f"""# Résumé: {state['user_request']}

## Points clés:
- Point principal 1
- Point principal 2  
- Point principal 3

## Conclusion:
Ce résumé présente les éléments essentiels du sujet demandé.""",
                
                "email": f"""Objet: {state['user_request']}

Cher(e) destinataire,

J'espère que ce message vous trouve bien.

[Contenu principal de l'email]

Cordialement,
[Votre nom]""",
                
                "code": f"""# Code Python pour: {state['user_request']}

def main():
    \"\"\"
    Fonction principale pour traiter la demande.
    \"\"\"
    print("Début du traitement...")
    
    # Ajoutez votre logique ici
    result = process_request()
    
    print(f"Résultat: {{result}}")
    return result

def process_request():
    \"\"\"
    Traite la demande spécifique.
    \"\"\"
    # Implémentez votre logique ici
    return "Traitement terminé"

if __name__ == "__main__":
    main()""",
                
                "general": f"""# Contenu généré pour: {state['user_request']}

## Introduction
Ce contenu a été généré en réponse à votre demande.

## Contenu principal
[Insérez ici le contenu principal]

## Conclusion
Merci pour votre demande."""
            }
            
            generated_content = templates.get(content_type, templates["general"])
        
    except Exception as e:
        generated_content = f"Erreur de génération: {str(e)}\n\nContenu de secours généré localement."
    
    # Dispatch custom event
    generation_event = dispatch_event(
        "content_generated",
        f"🤖 **Contenu généré**\n\n**Type:** {content_type}\n**Méthode:** {'LLM' if use_llm else 'Template'}\n\n**Contenu:**\n{generated_content[:500]}{'...' if len(generated_content) > 500 else ''}",
        {"content_type": content_type, "content_length": len(generated_content), "use_llm": use_llm}
    )
    
    # Add event to state
    events = state.get("events", [])
    events.append(generation_event)
    
    return {
        **state,
        "generated_content": generated_content,
        "step": "generated",
        "events": events
    }

def human_review_node(state: WorkflowState) -> WorkflowState:
    """Nœud d'interruption pour révision humaine"""
    print("👤 Interruption pour révision humaine...")
    
    # Dispatch custom event for human review request
    review_event = dispatch_event(
        "human_review_requested",
        f"👤 **Révision humaine requise**\n\n**Demande:** {state['user_request']}\n**Type de contenu:** {state['metadata'].get('content_type', 'general')}\n**Méthode de génération:** {'LLM' if state.get('use_llm', True) else 'Template'}\n\nLe contenu généré attend votre validation et modification si nécessaire.",
        {"content_type": state["metadata"].get("content_type", "general"), "use_llm": state.get('use_llm', True)}
    )
    
    # Add event to state
    events = state.get("events", [])
    events.append(review_event)
    
    # Créer les données d'interruption
    interrupt_payload = {
        "task": "Veuillez réviser et modifier le contenu généré si nécessaire",
        "user_request": state["user_request"],
        "analysis": state["analysis"],
        "generated_content": state["generated_content"],
        "content_type": state["metadata"].get("content_type", "general"),
        "use_llm": state.get("use_llm", True),
        "interruption_type": "human_review",
        "timestamp": time.time()
    }
    
    # INTERRUPTION : Le workflow s'arrête ici et attend l'input humain
    result = interrupt(interrupt_payload)
    
    # Cette ligne ne s'exécute qu'après la reprise avec Command(resume=...)
    return {
        **state,
        "human_feedback": result.get("human_feedback", ""),
        "generated_content": result.get("edited_content", state["generated_content"]),
        "step": "reviewed",
        "events": events
    }

def finalize_content_node(state: WorkflowState) -> WorkflowState:
    """Finalise le contenu après révision humaine"""
    print("✅ Finalisation du contenu...")
    
    # Intégrer le feedback humain
    final_result = state["generated_content"]
    
    if state.get("human_feedback"):
        final_result += f"\n\n--- Commentaires de révision ---\n{state['human_feedback']}"
    
    # Dispatch custom event for finalization
    finalization_event = dispatch_event(
        "content_finalized",
        f"✅ **Contenu finalisé**\n\n**Demande originale:** {state['user_request']}\n**Feedback humain:** {'Oui' if state.get('human_feedback') else 'Non'}\n\nLe workflow est terminé avec succès !",
        {"has_feedback": bool(state.get("human_feedback")), "final_length": len(final_result)}
    )
    
    # Add event to state
    events = state.get("events", [])
    events.append(finalization_event)
    
    return {
        **state,
        "final_result": final_result,
        "step": "finalized",
        "events": events
    }

# Construction du graphe LangGraph
@st.cache_resource
def create_workflow():
    """Crée et compile le workflow LangGraph avec gestion des interruptions"""
    builder = StateGraph(WorkflowState)
    
    # Ajouter les nœuds
    builder.add_node("analyze_request", analyze_request_node)
    builder.add_node("llm_decision", llm_decision_node)
    builder.add_node("generate_content", generate_content_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("finalize_content", finalize_content_node)
    
    # Définir le flow
    builder.set_entry_point("analyze_request")
    builder.add_edge("analyze_request", "llm_decision")
    builder.add_edge("llm_decision", "generate_content")
    builder.add_edge("generate_content", "human_review")
    builder.add_edge("human_review", "finalize_content")
    builder.add_edge("finalize_content", END)
    
    # Compiler avec checkpointer pour supporter les interruptions
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)

# Interface Streamlit principale
def main():
    init_session_state()
    
    # Titre et description
    st.title("🤖 Assistant IA avec Interruptions LangGraph")
    st.markdown("---")
    st.markdown("**Workflow intelligent avec validation humaine en temps réel**")
    
    # Sidebar pour les contrôles
    with st.sidebar:
        st.header("🎛️ Contrôles du Workflow")
        
        # Statut actuel
        status = st.session_state.workflow_state['current_step']
        if status == 'idle':
            st.markdown('<div class="status-success">💤 En attente</div>', unsafe_allow_html=True)
        elif status == 'processing':
            st.markdown('<div class="status-waiting">⚙️ Traitement en cours...</div>', unsafe_allow_html=True)
        elif status == 'interrupted':
            # Check what type of interruption
            interrupt_data = st.session_state.workflow_state.get('interrupt_data')
            if interrupt_data and len(interrupt_data) > 0:
                ui_data = interrupt_data[-1].value
                interruption_type = ui_data.get('interruption_type', 'human_review')
                
                if interruption_type == 'llm_decision':
                    st.markdown('<div class="status-waiting">🤖 En attente de décision LLM</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="status-waiting">⏸️ En attente de révision</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="status-waiting">⏸️ En attente de révision</div>', unsafe_allow_html=True)
        elif status == 'completed':
            st.markdown('<div class="status-success">✅ Terminé</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Panel des événements
        st.subheader("📊 Événements du Workflow")
        events = st.session_state.workflow_state.get('events', [])
        
        if events:
            for i, event in enumerate(events[-5:]):  # Show last 5 events
                event_type = event.get('type', 'unknown')
                timestamp = event.get('data', {}).get('timestamp', 0)
                time_str = time.strftime('%H:%M:%S', time.localtime(timestamp))
                
                # Color coding for different event types
                if 'analysis' in event_type:
                    icon = "🔍"
                    color = "success"
                elif 'llm_decision' in event_type:
                    icon = "🤖"
                    color = "warning"
                elif 'generated' in event_type:
                    icon = "🤖"
                    color = "info"
                elif 'review' in event_type:
                    icon = "👤"
                    color = "warning"
                elif 'finalized' in event_type:
                    icon = "✅"
                    color = "success"
                else:
                    icon = "📋"
                    color = "info"
                
                st.markdown(f"""
                <div class="status-{color}">
                    {icon} {event_type.replace('_', ' ').title()}
                    <br><small>{time_str}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Aucun événement pour le moment")
        
        st.markdown("---")
        
        # Bouton reset
        if st.button("🔄 Nouveau Workflow", use_container_width=True):
            reset_workflow()
        
        # Informations de debug
        with st.expander("🔧 Debug Info"):
            st.json({
                "thread_id": st.session_state.workflow_state.get('current_thread_id'),
                "interrupted": st.session_state.workflow_state.get('interrupted', False),
                "completed": st.session_state.workflow_state.get('workflow_completed', False),
                "current_step": st.session_state.workflow_state.get('current_step', 'idle'),
                "events_count": len(events)
            })
    
    # Interface principale
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 Interface Utilisateur")
        
        # Progress indicator for workflow steps
        if st.session_state.workflow_state['current_step'] != 'idle':
            st.subheader("📈 Progression du Workflow")
            
            steps = ['start', 'analyzed', 'llm_decided', 'generated', 'reviewed', 'finalized']
            current_step = st.session_state.workflow_state['current_step']
            
            if current_step in steps:
                current_index = steps.index(current_step)
                progress = (current_index + 1) / len(steps)
                
                st.progress(progress)
                
                # Show step labels
                cols = st.columns(len(steps))
                for i, step in enumerate(steps):
                    with cols[i]:
                        if i <= current_index:
                            st.markdown(f"✅ {step.title()}")
                        else:
                            st.markdown(f"⏳ {step.title()}")
        
        render_main_interface()
    
    with col2:
        st.header("🔍 Panneau de Révision")
        render_review_panel()

def render_main_interface():
    """Affiche l'interface principale de saisie"""
    
    # Afficher l'historique des messages
    for msg in st.session_state.messages:
        if msg['type'] == 'user':
            st.chat_message("user").write(msg['content'])
        elif msg['type'] == 'assistant':
            st.chat_message("assistant").write(msg['content'])
        elif msg['type'] == 'system':
            st.info(f"🔄 {msg['content']}")
        elif msg['type'] == 'event':
            # Display custom events with special styling
            st.chat_message("assistant").write(msg['content'])
            
            # Show metadata in an expander
            if msg.get('metadata'):
                with st.expander("📊 Métadonnées de l'événement"):
                    st.json(msg['metadata'])
    
    # Interface de saisie
    if not st.session_state.workflow_state.get('interrupted', False):
        
        # Zone de saisie principale
        user_input = st.chat_input("Décrivez ce que vous voulez que l'IA génère...")
        
        if user_input:
            handle_user_request(user_input)
        
        # Boutons d'exemples
        st.markdown("**💡 Exemples rapides:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📝 Résumé d'article"):
                handle_user_request("Crée un résumé professionnel sur l'intelligence artificielle")
        
        with col2:
            if st.button("📧 Email professionnel"):
                handle_user_request("Rédige un email de suivi client")
        
        with col3:
            if st.button("💻 Code Python"):
                handle_user_request("Génère du code pour analyser un CSV")

def render_review_panel():
    """Affiche le panneau de révision pour les interruptions"""
    
    if st.session_state.workflow_state.get('interrupted', False):
        interrupt_data = st.session_state.workflow_state.get('interrupt_data')
        
        if interrupt_data:
            ui_data = interrupt_data[-1].value
            interruption_type = ui_data.get('interruption_type', 'human_review')
            
            if interruption_type == 'llm_decision':
                # Panel for LLM decision
                st.markdown('<div class="interrupt-card">', unsafe_allow_html=True)
                st.markdown("### 🤖 Décision LLM")
                st.markdown("Décidez si vous voulez utiliser l'IA pour générer le contenu...")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Afficher les informations
                st.markdown("**📋 Demande originale:**")
                st.info(ui_data.get('user_request', 'N/A'))
                
                st.markdown("**🔍 Analyse:**")
                st.write(ui_data.get('analysis', 'N/A'))
                
                st.markdown("**📝 Type de contenu:**")
                st.write(ui_data.get('content_type', 'N/A'))
                
                # Boutons de décision
                st.markdown("**🤖 Voulez-vous utiliser l'IA ?**")
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Oui, utiliser l'IA", use_container_width=True, type="primary"):
                        resume_llm_decision(True)
                
                with col2:
                    if st.button("❌ Non, générer sans IA", use_container_width=True):
                        resume_llm_decision(False)
            
            else:
                # Panel for human review (existing functionality)
                st.markdown('<div class="interrupt-card">', unsafe_allow_html=True)
                st.markdown("### ⏸️ Révision Requise")
                st.markdown("Le workflow attend votre validation...")
                st.markdown('</div>', unsafe_allow_html=True)
                
                # Afficher les informations
                st.markdown("**📋 Demande originale:**")
                st.info(ui_data.get('user_request', 'N/A'))
                
                st.markdown("**🔍 Analyse:**")
                st.write(ui_data.get('analysis', 'N/A'))
                
                st.markdown("**🤖 Méthode de génération:**")
                use_llm = ui_data.get('use_llm', True)
                st.write(f"{'LLM' if use_llm else 'Template'}")
                
                st.markdown("**🤖 Contenu généré:**")
                generated_content = ui_data.get('generated_content', '')
                
                # Zone d'édition du contenu
                edited_content = st.text_area(
                    "Éditez le contenu si nécessaire:",
                    value=generated_content,
                    height=300,
                    key="content_editor"
                )
                
                # Feedback optionnel
                human_feedback = st.text_area(
                    "💬 Commentaires (optionnel):",
                    placeholder="Ajoutez vos commentaires sur les modifications...",
                    height=100,
                    key="feedback_editor"
                )
                
                # Boutons d'action
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("✅ Approuver", use_container_width=True, type="primary"):
                        resume_workflow(edited_content, human_feedback)
                
                with col2:
                    if st.button("❌ Rejeter", use_container_width=True):
                        reject_workflow(human_feedback)
    
    else:
        st.info("🔄 Aucune révision en attente")
        
        # Historique des exécutions
        if st.session_state.workflow_state.get('execution_history'):
            with st.expander("📚 Historique"):
                for i, execution in enumerate(st.session_state.workflow_state['execution_history']):
                    st.write(f"**Exécution {i+1}:** {execution.get('user_request', 'N/A')[:50]}...")

def handle_user_request(user_input: str):
    """Traite une nouvelle demande utilisateur"""
    
    # Ajouter le message utilisateur
    st.session_state.messages.append({
        'type': 'user',
        'content': user_input,
        'timestamp': time.time()
    })
    
    # Initialiser le workflow
    st.session_state.workflow_state.update({
        'current_thread_id': str(uuid.uuid4()),
        'interrupted': False,
        'workflow_completed': False,
        'current_step': 'processing'
    })
    
    # Créer ou récupérer le graphe
    if st.session_state.graph is None:
        st.session_state.graph = create_workflow()
    
    # Préparer l'état initial
    initial_state = {
        "user_request": user_input,
        "analysis": "",
        "generated_content": "",
        "human_feedback": "",
        "final_result": "",
        "step": "start",
        "metadata": {},
        "events": [],
        "use_llm": True,
        "llm_decision_made": False
    }
    
    # Configuration du thread
    config = {"configurable": {"thread_id": st.session_state.workflow_state['current_thread_id']}}
    
    try:
        # Exécuter jusqu'à l'interruption
        with st.spinner("🔄 Traitement en cours..."):
            result = st.session_state.graph.invoke(initial_state, config=config)
        
        # Process events and add them to messages
        if "events" in result:
            # Update workflow state events
            update_workflow_events(result["events"])
            
            # Add events to messages
            for event in result["events"]:
                st.session_state.messages.append({
                    'type': 'event',
                    'event_type': event['type'],
                    'content': event['data']['content'],
                    'timestamp': event['data']['timestamp'],
                    'metadata': event['data'].get('metadata', {})
                })
        
        # Vérifier s'il y a une interruption
        if "__interrupt__" in result:
            st.session_state.workflow_state.update({
                'interrupted': True,
                'interrupt_data': result["__interrupt__"],
                'current_step': 'interrupted'
            })
            
            # Check interruption type
            interrupt_data = result["__interrupt__"]
            if interrupt_data and len(interrupt_data) > 0:
                ui_data = interrupt_data[-1].value
                interruption_type = ui_data.get('interruption_type', 'human_review')
                
                if interruption_type == 'llm_decision':
                    st.session_state.messages.append({
                        'type': 'system',
                        'content': 'Décision LLM requise - En attente de votre choix',
                        'timestamp': time.time()
                    })
                else:
                    st.session_state.messages.append({
                        'type': 'system',
                        'content': 'Contenu généré - En attente de révision',
                        'timestamp': time.time()
                    })
        else:
            # Workflow terminé sans interruption (ne devrait pas arriver dans ce cas)
            complete_workflow(result)
    
    except Exception as e:
        st.error(f"Erreur lors du traitement: {str(e)}")
        st.session_state.workflow_state['current_step'] = 'idle'
    
    st.rerun()

def resume_llm_decision(use_llm: bool):
    """Reprend le workflow avec la décision LLM"""
    
    config = {"configurable": {"thread_id": st.session_state.workflow_state['current_thread_id']}}
    
    try:
        with st.spinner("🔄 Traitement de la décision..."):
            # Reprendre avec Command(resume=...)
            resume_data = {
                "use_llm": use_llm
            }
            
            result = st.session_state.graph.invoke(
                Command(resume=resume_data),
                config=config
            )
        
        # Process events from resumed workflow
        if "events" in result:
            # Update workflow state events
            update_workflow_events(result["events"])
            
            # Add events to messages
            for event in result["events"]:
                st.session_state.messages.append({
                    'type': 'event',
                    'event_type': event['type'],
                    'content': event['data']['content'],
                    'timestamp': event['data']['timestamp'],
                    'metadata': event['data'].get('metadata', {})
                })
        
        # Check if there's another interruption (human review)
        if "__interrupt__" in result:
            st.session_state.workflow_state.update({
                'interrupted': True,
                'interrupt_data': result["__interrupt__"],
                'current_step': 'interrupted'
            })
            
            st.session_state.messages.append({
                'type': 'system',
                'content': f'Décision LLM prise: {"Avec IA" if use_llm else "Sans IA"} - En attente de révision',
                'timestamp': time.time()
            })
        else:
            # Workflow completed
            complete_workflow(result)
    
    except Exception as e:
        st.error(f"Erreur lors de la reprise: {str(e)}")

def resume_workflow(edited_content: str, human_feedback: str = ""):
    """Reprend le workflow avec le contenu édité"""
    
    config = {"configurable": {"thread_id": st.session_state.workflow_state['current_thread_id']}}
    
    try:
        with st.spinner("🔄 Finalisation en cours..."):
            # Reprendre avec Command(resume=...)
            resume_data = {
                "edited_content": edited_content,
                "human_feedback": human_feedback
            }
            
            final_result = st.session_state.graph.invoke(
                Command(resume=resume_data),
                config=config
            )
        
        # Process events from resumed workflow
        if "events" in final_result:
            # Update workflow state events
            update_workflow_events(final_result["events"])
            
            # Add events to messages
            for event in final_result["events"]:
                st.session_state.messages.append({
                    'type': 'event',
                    'event_type': event['type'],
                    'content': event['data']['content'],
                    'timestamp': event['data']['timestamp'],
                    'metadata': event['data'].get('metadata', {})
                })
        
        complete_workflow(final_result, human_feedback)
    
    except Exception as e:
        st.error(f"Erreur lors de la reprise: {str(e)}")

def reject_workflow(feedback: str = ""):
    """Rejette le workflow avec feedback"""
    
    st.session_state.messages.append({
        'type': 'system',
        'content': f'Workflow rejeté. {feedback}',
        'timestamp': time.time()
    })
    
    reset_workflow()

def complete_workflow(result: Dict[str, Any], feedback: str = ""):
    """Termine le workflow avec succès"""
    
    final_content = result.get("final_result", "Contenu non disponible")
    
    # Process any remaining events from the final result
    if "events" in result:
        # Update workflow state events
        update_workflow_events(result["events"])
        
        for event in result["events"]:
            # Only add events that haven't been processed yet
            event_id = f"{event['type']}_{event['data']['timestamp']}"
            existing_events = [msg for msg in st.session_state.messages if msg.get('type') == 'event']
            if not any(f"{msg['event_type']}_{msg['timestamp']}" == event_id for msg in existing_events):
                st.session_state.messages.append({
                    'type': 'event',
                    'event_type': event['type'],
                    'content': event['data']['content'],
                    'timestamp': event['data']['timestamp'],
                    'metadata': event['data'].get('metadata', {})
                })
    
    # Ajouter le résultat final
    st.session_state.messages.append({
        'type': 'assistant',
        'content': final_content,
        'timestamp': time.time()
    })
    
    if feedback:
        st.session_state.messages.append({
            'type': 'system',
            'content': f'✅ Workflow terminé avec feedback: {feedback}',
            'timestamp': time.time()
        })
    else:
        st.session_state.messages.append({
            'type': 'system',
            'content': '✅ Workflow terminé avec succès',
            'timestamp': time.time()
        })
    
    # Sauvegarder dans l'historique
    execution_record = {
        'user_request': result.get('user_request', ''),
        'final_result': final_content,
        'timestamp': time.time(),
        'feedback': feedback
    }
    
    if 'execution_history' not in st.session_state.workflow_state:
        st.session_state.workflow_state['execution_history'] = []
    
    st.session_state.workflow_state['execution_history'].append(execution_record)
    
    # Réinitialiser l'état
    st.session_state.workflow_state.update({
        'interrupted': False,
        'interrupt_data': None,
        'workflow_completed': True,
        'current_step': 'completed'
    })
    
    st.rerun()

def reset_workflow():
    """Réinitialise complètement le workflow"""
    st.session_state.workflow_state = {
        'current_thread_id': None,
        'interrupted': False,
        'interrupt_data': None,
        'workflow_completed': False,
        'execution_history': st.session_state.workflow_state.get('execution_history', []),
        'current_step': 'idle',
        'events': [],
        'use_llm': True, # Reset LLM preference
        'llm_decision_made': False # Reset LLM decision flag
    }
    st.session_state.messages = []
    st.rerun()

# Point d'entrée principal
if __name__ == "__main__":
    main()