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
            'current_step': 'idle'
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
    
    return {
        **state,
        "analysis": analysis,
        "step": "analyzed",
        "metadata": {**state.get("metadata", {}), "content_type": content_type}
    }

def generate_content_node(state: WorkflowState) -> WorkflowState:
    """Génère le contenu initial avec l'IA"""
    print(f"🤖 Génération de contenu pour: {state['analysis']}")
    
    try:
        llm = get_llm()
        content_type = state["metadata"].get("content_type", "general")
        
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
        
    except Exception as e:
        generated_content = f"Erreur de génération: {str(e)}\n\nContenu de secours généré localement."
    
    return {
        **state,
        "generated_content": generated_content,
        "step": "generated"
    }

def human_review_node(state: WorkflowState) -> WorkflowState:
    """Nœud d'interruption pour révision humaine"""
    print("👤 Interruption pour révision humaine...")
    
    # Créer les données d'interruption
    interrupt_payload = {
        "task": "Veuillez réviser et modifier le contenu généré si nécessaire",
        "user_request": state["user_request"],
        "analysis": state["analysis"],
        "generated_content": state["generated_content"],
        "content_type": state["metadata"].get("content_type", "general"),
        "timestamp": time.time()
    }
    
    # INTERRUPTION : Le workflow s'arrête ici et attend l'input humain
    result = interrupt(interrupt_payload)
    
    # Cette ligne ne s'exécute qu'après la reprise avec Command(resume=...)
    return {
        **state,
        "human_feedback": result.get("human_feedback", ""),
        "generated_content": result.get("edited_content", state["generated_content"]),
        "step": "reviewed"
    }

def finalize_content_node(state: WorkflowState) -> WorkflowState:
    """Finalise le contenu après révision humaine"""
    print("✅ Finalisation du contenu...")
    
    # Intégrer le feedback humain
    final_result = state["generated_content"]
    
    if state.get("human_feedback"):
        final_result += f"\n\n--- Commentaires de révision ---\n{state['human_feedback']}"
    
    return {
        **state,
        "final_result": final_result,
        "step": "finalized"
    }

# Construction du graphe LangGraph
@st.cache_resource
def create_workflow():
    """Crée et compile le workflow LangGraph avec gestion des interruptions"""
    builder = StateGraph(WorkflowState)
    
    # Ajouter les nœuds
    builder.add_node("analyze_request", analyze_request_node)
    builder.add_node("generate_content", generate_content_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("finalize_content", finalize_content_node)
    
    # Définir le flow
    builder.set_entry_point("analyze_request")
    builder.add_edge("analyze_request", "generate_content")
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
            st.markdown('<div class="status-waiting">⏸️ En attente de révision</div>', unsafe_allow_html=True)
        elif status == 'completed':
            st.markdown('<div class="status-success">✅ Terminé</div>', unsafe_allow_html=True)
        
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
                "current_step": st.session_state.workflow_state.get('current_step', 'idle')
            })
    
    # Interface principale
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("💬 Interface Utilisateur")
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
            st.markdown('<div class="interrupt-card">', unsafe_allow_html=True)
            st.markdown("### ⏸️ Révision Requise")
            st.markdown("Le workflow attend votre validation...")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Afficher les informations
            st.markdown("**📋 Demande originale:**")
            ui_data = interrupt_data[-1].value
            st.info(ui_data.get('user_request', 'N/A'))
            
            st.markdown("**🔍 Analyse:**")

            st.write(ui_data.get('analysis', 'N/A'))
            
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
        "metadata": {}
    }
    
    # Configuration du thread
    config = {"configurable": {"thread_id": st.session_state.workflow_state['current_thread_id']}}
    
    try:
        # Exécuter jusqu'à l'interruption
        with st.spinner("🔄 Traitement en cours..."):
            result = st.session_state.graph.invoke(initial_state, config=config)
        
        # Vérifier s'il y a une interruption
        if "__interrupt__" in result:
            st.session_state.workflow_state.update({
                'interrupted': True,
                'interrupt_data': result["__interrupt__"],
                'current_step': 'interrupted'
            })
            
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
        'current_step': 'idle'
    }
    st.session_state.messages = []
    st.rerun()

# Point d'entrée principal
if __name__ == "__main__":
    main()