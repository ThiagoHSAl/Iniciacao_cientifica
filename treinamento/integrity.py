import os

def limpar_subset(diretorio_raiz, nome_subset):
    """
    Processa um subconjunto específico (train, valid ou test).
    """
    path_images = os.path.join(diretorio_raiz, nome_subset, 'images')
    path_labels = os.path.join(diretorio_raiz, nome_subset, 'labels')
    
    # Extensões de imagem aceitas
    extensoes_imagem = ('.jpg', '.jpeg', '.png', '.bmp')

    print(f"\n{'='*20} PROCESSANDO: {nome_subset.upper()} {'='*20}")

    # Verifica se as pastas existem neste subset
    if not os.path.exists(path_images) or not os.path.exists(path_labels):
        print(f"AVISO: Pastas 'images' e/ou 'labels' não encontradas em '{nome_subset}'. Pulando.")
        return

    # 1. Mapear o "nome base" de todas as imagens existentes
    bases_imagens = set()
    arquivos_imagem_completos = [] 
    
    for f in os.listdir(path_images):
        if f.lower().endswith(extensoes_imagem):
            nome_base = os.path.splitext(f)[0]
            bases_imagens.add(nome_base)
            arquivos_imagem_completos.append(f)

    # --- ETAPA 1: Deletar Labels órfãos (sem imagem) ---
    print(f"[{nome_subset}] Verificando Labels sem imagem...")
    labels_deletados = 0
    
    if os.path.exists(path_labels):
        for arquivo_label in os.listdir(path_labels):
            if arquivo_label.endswith('.txt'):
                nome_base_label = os.path.splitext(arquivo_label)[0]
                
                # Se o nome do label NÃO está na lista de imagens
                if nome_base_label not in bases_imagens:
                    caminho_completo_label = os.path.join(path_labels, arquivo_label)
                    try:
                        os.remove(caminho_completo_label)
                        print(f"  [DELETADO] {nome_subset}/labels/{arquivo_label}")
                        labels_deletados += 1
                    except Exception as e:
                        print(f"  [ERRO] Ao deletar {arquivo_label}: {e}")
    
    print(f"  -> Total de labels deletados em {nome_subset}: {labels_deletados}")

    # --- ETAPA 2: Retornar Imagens sem Label (Background Images) ---
    print(f"[{nome_subset}] Verificando Imagens sem Label...")
    
    # Atualiza a lista de labels existentes
    bases_labels_existentes = set()
    if os.path.exists(path_labels):
        for f in os.listdir(path_labels):
            if f.endswith('.txt'):
                bases_labels_existentes.add(os.path.splitext(f)[0])
    
    imagens_sem_label = []
    
    for arquivo_imagem in arquivos_imagem_completos:
        nome_base_imagem = os.path.splitext(arquivo_imagem)[0]
        
        if nome_base_imagem not in bases_labels_existentes:
            imagens_sem_label.append(arquivo_imagem)

    if len(imagens_sem_label) > 0:
        print(f"  -> Encontradas {len(imagens_sem_label)} imagens sem label (Background) em {nome_subset}:")
        for img in imagens_sem_label:
            print(f"     [SEM LABEL] {img}")
    else:
        print(f"  -> Todas as imagens de {nome_subset} possuem label.")

def main():
    diretorio_atual = os.getcwd()
    print(f"Iniciando varredura na raiz: {diretorio_atual}")
    
    # Lista dos subsets padrões do YOLO
    subsets = ['train', 'valid', 'test']
    
    for subset in subsets:
        limpar_subset(diretorio_atual, subset)

    print("\n--- VARREDURA COMPLETA CONCLUÍDA ---")

if __name__ == "__main__":
    main()

