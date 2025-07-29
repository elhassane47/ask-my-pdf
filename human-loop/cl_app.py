import streamlit as st
import pandas as pd
import io
from typing import Optional, Tuple

# Configuration de la page
st.set_page_config(
    page_title="📁 Workflow Sequential File Upload",
    page_icon="🔄",
    layout="wide"
)

# CSS personnalisé pour améliorer l'interface
st.markdown("""
<style>
    .step-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
        text-align: center;
    }
    .step-completed {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
        margin: 10px 0;
        text-align: center;
    }
    .step-pending {
        background: #f8f9fa;
        border: 2px dashed #dee2e6;
        padding: 15px;
        border-radius: 10px;
        color: #6c757d;
        margin: 10px 0;
        text-align: center;
    }
    .file-info {
        background: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

def init_session_state():
    """Initialise l'état de la session"""
    if 'workflow_step' not in st.session_state:
        st.session_state.workflow_step = 1
    
    if 'selected_region' not in st.session_state:
        st.session_state.selected_region = None
    
    if 'first_file_content' not in st.session_state:
        st.session_state.first_file_content = None
    
    if 'first_file_name' not in st.session_state:
        st.session_state.first_file_name = None
    
    if 'second_file_content' not in st.session_state:
        st.session_state.second_file_content = None
    
    if 'second_file_name' not in st.session_state:
        st.session_state.second_file_name = None
    
    if 'has_second_file' not in st.session_state:
        st.session_state.has_second_file = None
    
    if 'concatenated_content' not in st.session_state:
        st.session_state.concatenated_content = None

def read_file_content(uploaded_file) -> Optional[str]:
    """Lit le contenu d'un fichier uploadé"""
    try:
        if uploaded_file.type == "text/plain":
            # Fichier texte
            content = uploaded_file.read().decode('utf-8')
        elif uploaded_file.type == "text/csv":
            # Fichier CSV
            df = pd.read_csv(uploaded_file)
            content = df.to_string(index=False)
        elif uploaded_file.name.endswith('.sas'):
            # Fichier SAS
            content = uploaded_file.read().decode('utf-8')
        elif uploaded_file.name.endswith(('.py', '.sql', '.r')):
            # Autres fichiers de code
            content = uploaded_file.read().decode('utf-8')
        else:
            # Essayer de lire comme texte
            content = uploaded_file.read().decode('utf-8')
        
        return content
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier: {str(e)}")
        return None

def display_workflow_progress():
    """Affiche la progression du workflow"""
    st.markdown("### 🔄 Progression du Workflow")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.session_state.workflow_step >= 1:
            if st.session_state.selected_region:
                st.markdown('<div class="step-completed">✅ Étape 1: Région sélectionnée</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="step-container">1️⃣ Sélection Région</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="step-pending">1️⃣ Sélection Région</div>', unsafe_allow_html=True)
    
    with col2:
        if st.session_state.workflow_step >= 2:
            if st.session_state.first_file_content:
                st.markdown('<div class="step-completed">✅ Étape 2: Premier fichier</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="step-container">2️⃣ Premier Fichier</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="step-pending">2️⃣ Premier Fichier</div>', unsafe_allow_html=True)
    
    with col3:
        if st.session_state.workflow_step >= 3:
            if st.session_state.has_second_file is not None:
                st.markdown('<div class="step-completed">✅ Étape 3: Choix second fichier</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="step-container">3️⃣ Second Fichier?</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="step-pending">3️⃣ Second Fichier?</div>', unsafe_allow_html=True)
    
    with col4:
        if st.session_state.workflow_step >= 4:
            if st.session_state.concatenated_content:
                st.markdown('<div class="step-completed">✅ Étape 4: Résultat final</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="step-container">4️⃣ Résultat Final</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="step-pending">4️⃣ Résultat Final</div>', unsafe_allow_html=True)

def step_1_region_selection():
    """Étape 1: Sélection de la région"""
    st.markdown("### 🌍 Étape 1: Sélection de la Région")
    
    # Sélecteur de région
    region_options = ["Sélectionnez une région...", "nordics", "netherlands"]
    
    selected_region = st.selectbox(
        "Choisissez votre région:",
        options=region_options,
        index=0 if not st.session_state.selected_region else region_options.index(st.session_state.selected_region),
        key="region_selector"
    )
    
    # Validation et passage à l'étape suivante
    if selected_region != "Sélectionnez une région...":
        if st.button("✅ Confirmer la région", type="primary"):
            st.session_state.selected_region = selected_region
            st.session_state.workflow_step = 2
            st.success(f"✅ Région sélectionnée: **{selected_region}**")
            st.rerun()
    else:
        st.info("👆 Veuillez sélectionner une région pour continuer")

def step_2_first_file_upload():
    """Étape 2: Upload du premier fichier"""
    st.markdown("### 📁 Étape 2: Upload du Premier Fichier")
    
    # Afficher la région sélectionnée
    st.markdown(f'<div class="file-info">🌍 <strong>Région sélectionnée:</strong> {st.session_state.selected_region}</div>', unsafe_allow_html=True)
    
    # Upload du premier fichier
    first_file = st.file_uploader(
        "Uploadez votre premier fichier:",
        type=['txt', 'csv', 'sas', 'py', 'sql', 'r'],
        key="first_file_uploader"
    )
    
    if first_file is not None:
        # Lire le contenu du fichier
        file_content = read_file_content(first_file)
        
        if file_content:
            # Afficher les informations du fichier
            st.markdown("**📄 Informations du fichier:**")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Nom", first_file.name)
            with col2:
                st.metric("Taille", f"{first_file.size} bytes")
            with col3:
                st.metric("Type", first_file.type)
            
            # Aperçu du contenu
            with st.expander("👀 Aperçu du contenu"):
                st.text_area("Contenu du fichier:", file_content[:1000] + "..." if len(file_content) > 1000 else file_content, height=200, disabled=True)
            
            # Confirmer et passer à l'étape suivante
            if st.button("✅ Confirmer le premier fichier", type="primary"):
                st.session_state.first_file_content = file_content
                st.session_state.first_file_name = first_file.name
                st.session_state.workflow_step = 3
                st.success(f"✅ Premier fichier traité: **{first_file.name}**")
                st.rerun()

def step_3_second_file_choice():
    """Étape 3: Choix du second fichier"""
    st.markdown("### 🤔 Étape 3: Avez-vous un Second Fichier?")
    
    # Résumé des étapes précédentes
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="file-info">🌍 <strong>Région:</strong> {st.session_state.selected_region}</div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="file-info">📁 <strong>Premier fichier:</strong> {st.session_state.first_file_name}</div>', unsafe_allow_html=True)
    
    # Question sur le second fichier
    st.markdown("**Souhaitez-vous ajouter un second fichier pour concatener avec le premier?**")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Oui, j'ai un second fichier", use_container_width=True, type="primary"):
            st.session_state.has_second_file = True
            st.session_state.workflow_step = 4
            st.rerun()
    
    with col2:
        if st.button("❌ Non, continuer avec un seul fichier", use_container_width=True):
            st.session_state.has_second_file = False
            # Directement finaliser avec un seul fichier
            st.session_state.concatenated_content = st.session_state.first_file_content
            st.session_state.workflow_step = 4
            st.rerun()

def step_4_second_file_upload_or_finalize():
    """Étape 4: Upload du second fichier ou finalisation"""
    if st.session_state.has_second_file:
        st.markdown("### 📁 Étape 4: Upload du Second Fichier")
        
        # Résumé
        st.markdown("**📋 Résumé actuel:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="file-info">🌍 <strong>Région:</strong> {st.session_state.selected_region}</div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="file-info">📁 <strong>Premier fichier:</strong> {st.session_state.first_file_name}</div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="file-info">📊 <strong>Caractères:</strong> {len(st.session_state.first_file_content)}</div>', unsafe_allow_html=True)
        
        # Upload du second fichier
        second_file = st.file_uploader(
            "Uploadez votre second fichier:",
            type=['txt', 'csv', 'sas', 'py', 'sql', 'r'],
            key="second_file_uploader"
        )
        
        if second_file is not None:
            # Lire le contenu du second fichier
            second_file_content = read_file_content(second_file)
            
            if second_file_content:
                # Afficher les informations du second fichier
                st.markdown("**📄 Informations du second fichier:**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Nom", second_file.name)
                with col2:
                    st.metric("Taille", f"{second_file.size} bytes")
                with col3:
                    st.metric("Type", second_file.type)
                
                # Aperçu du contenu
                with st.expander("👀 Aperçu du contenu du second fichier"):
                    st.text_area("Contenu:", second_file_content[:1000] + "..." if len(second_file_content) > 1000 else second_file_content, height=200, disabled=True)
                
                # Confirmer et concatener
                if st.button("🔗 Concatener les fichiers", type="primary"):
                    # Concatenation avec séparateur
                    separator = f"\n\n{'='*50}\n📁 FICHIER 2: {second_file.name}\n{'='*50}\n\n"
                    concatenated = f"📁 FICHIER 1: {st.session_state.first_file_name}\n{'='*50}\n\n{st.session_state.first_file_content}{separator}{second_file_content}"
                    
                    st.session_state.second_file_content = second_file_content
                    st.session_state.second_file_name = second_file.name
                    st.session_state.concatenated_content = concatenated
                    st.success("✅ Fichiers concatenés avec succès!")
                    st.rerun()
    
    # Affichage du résultat final
    if st.session_state.concatenated_content:
        display_final_result()

def display_final_result():
    """Affiche le résultat final"""
    st.markdown("### 🎉 Résultat Final")
    
    # Statistiques finales
    st.markdown("**📊 Statistiques:**")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Région", st.session_state.selected_region)
    with col2:
        st.metric("Fichiers traités", "2" if st.session_state.second_file_content else "1")
    with col3:
        st.metric("Caractères totaux", len(st.session_state.concatenated_content))
    with col4:
        st.metric("Lignes totales", len(st.session_state.concatenated_content.split('\n')))
    
    # Détails des fichiers
    with st.expander("📋 Détails des fichiers traités"):
        if st.session_state.first_file_name:
            st.write(f"**Premier fichier:** {st.session_state.first_file_name}")
        if st.session_state.second_file_name:
            st.write(f"**Second fichier:** {st.session_state.second_file_name}")
    
    # Contenu final
    st.markdown("**📄 Contenu Final (Concatené):**")
    st.text_area(
        "Résultat:", 
        st.session_state.concatenated_content, 
        height=400,
        key="final_content"
    )
    
    # Actions sur le résultat
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📋 Copier le contenu", use_container_width=True):
            st.write("Contenu prêt à être copié!")
    
    with col2:
        # Bouton de téléchargement
        filename = f"concatenated_{st.session_state.selected_region}_{len(st.session_state.concatenated_content)}_chars.txt"
        st.download_button(
            label="💾 Télécharger",
            data=st.session_state.concatenated_content,
            file_name=filename,
            mime="text/plain",
            use_container_width=True
        )
    
    with col3:
        if st.button("🔄 Recommencer", use_container_width=True):
            # Reset complet
            for key in ['workflow_step', 'selected_region', 'first_file_content', 
                       'first_file_name', 'second_file_content', 'second_file_name', 
                       'has_second_file', 'concatenated_content']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

def main():
    """Fonction principale"""
    init_session_state()
    
    st.title("📁 Workflow Sequential File Upload")
    st.markdown("---")
    
    # Affichage de la progression
    display_workflow_progress()
    st.markdown("---")
    
    # Navigation selon l'étape
    if st.session_state.workflow_step == 1:
        step_1_region_selection()
    
    elif st.session_state.workflow_step == 2:
        step_2_first_file_upload()
    
    elif st.session_state.workflow_step == 3:
        step_3_second_file_choice()
    
    elif st.session_state.workflow_step == 4:
        step_4_second_file_upload_or_finalize()
    
    # Sidebar avec informations
    with st.sidebar:
        st.header("📊 État du Workflow")
        st.write(f"**Étape actuelle:** {st.session_state.workflow_step}/4")
        
        if st.session_state.selected_region:
            st.success(f"🌍 Région: {st.session_state.selected_region}")
        
        if st.session_state.first_file_name:
            st.success(f"📁 Fichier 1: {st.session_state.first_file_name}")
        
        if st.session_state.second_file_name:
            st.success(f"📁 Fichier 2: {st.session_state.second_file_name}")
        
        st.markdown("---")
        st.markdown("**🔧 Types de fichiers supportés:**")
        st.markdown("- `.txt` - Fichiers texte")
        st.markdown("- `.csv` - Fichiers CSV")
        st.markdown("- `.sas` - Code SAS")  
        st.markdown("- `.py` - Code Python")
        st.markdown("- `.sql` - Requêtes SQL")
        st.markdown("- `.r` - Code R")

if __name__ == "__main__":
    main()