"""Playbooks de réponse — modèles réutilisables, bilingues FR/JP.

Insérables dans l'inbox (bouton « Modèles ») pour les tâches récurrentes du
négoce Hikaru. L'humain choisit, ajuste, puis valide avant envoi.
`{x}` = champ à compléter par l'agent.
"""

PLAYBOOKS = [
    {
        "key": "mercuriale",
        "label": "Envoi mercuriale",
        "fr": "Bonjour,\nVoici notre grille tarifaire grossiste en vigueur (en pièce jointe). "
              "N'hésitez pas à me préciser les quantités souhaitées, je vous établis un devis.\nBien à vous,",
        "jp": "こんにちは。\n最新の卸価格表を添付いたします。\nご希望の数量をお知らせいただければ、お見積りをお送りします。\nよろしくお願いいたします。",
    },
    {
        "key": "prix",
        "label": "Réponse prix",
        "fr": "Bonjour,\nPour {produit}, le tarif est de {prix} € HT l'unité (dégressif selon volume). "
              "Souhaitez-vous que je réserve une quantité ?\nBien à vous,",
        "jp": "こんにちは。\n{produit} の価格は 1個あたり {prix} 円（数量割引あり）です。\nご希望であれば在庫を確保いたします。\nよろしくお願いいたします。",
    },
    {
        "key": "dispo",
        "label": "Dispo / restock",
        "fr": "Bonjour,\n{produit} est {statut} en stock. {complement}\nJe peux vous réserver {qte} — me le confirmez-vous ?\nBien à vous,",
        "jp": "こんにちは。\n{produit} は現在{statut}です。{complement}\n{qte} をお取り置きできますが、ご確認いただけますか。\nよろしくお願いいたします。",
    },
    {
        "key": "moq",
        "label": "MOQ grossiste",
        "fr": "Bonjour,\nNotre quantité minimale de commande (MOQ) pour {produit} est de {moq}. "
              "Le tarif grossiste s'applique dès ce seuil. Je vous prépare un devis ?\nBien à vous,",
        "jp": "こんにちは。\n{produit} の最低発注数量（MOQ）は {moq} です。\nこの数量から卸価格が適用されます。お見積りをご用意しましょうか。\nよろしくお願いいたします。",
    },
    {
        "key": "precommande",
        "label": "Précommande",
        "fr": "Bonjour,\nLa précommande de {produit} est ouverte. Livraison estimée {date}, "
              "acompte de {acompte}. Je vous réserve {qte} ?\nBien à vous,",
        "jp": "こんにちは。\n{produit} の予約を受付中です。お届け予定は {date}、前金は {acompte} です。\n{qte} をお取り置きしましょうか。\nよろしくお願いいたします。",
    },
    {
        "key": "suivi",
        "label": "Suivi commande",
        "fr": "Bonjour,\nVotre commande {ref} a été expédiée. Suivi : {tracking}. "
              "Livraison prévue {date}.\nBien à vous,",
        "jp": "こんにちは。\nご注文 {ref} を発送いたしました。追跡番号：{tracking}。お届け予定は {date} です。\nよろしくお願いいたします。",
    },
    {
        "key": "litige",
        "label": "Litige / SAV",
        "fr": "Bonjour,\nNavré pour ce désagrément. Pouvez-vous m'envoyer une photo des articles concernés "
              "et la référence commande ? Je traite le remplacement/avoir en priorité.\nBien à vous,",
        "jp": "こんにちは。\nご不便をおかけし申し訳ございません。該当商品の写真とご注文番号をお送りいただけますか。\n優先的に交換・返金の対応をいたします。\nよろしくお願いいたします。",
    },
    {
        "key": "onboarding",
        "label": "Ouverture compte revendeur",
        "fr": "Bonjour,\nAvec plaisir. Pour ouvrir un compte grossiste, il me faut : Kbis/n° TVA, "
              "coordonnées de facturation et de livraison. Je vous envoie ensuite la mercuriale.\nBien à vous,",
        "jp": "こんにちは。\n卸アカウント開設には、登記情報・VAT番号、請求先および配送先をお知らせください。\nその後、卸価格表をお送りします。\nよろしくお願いいたします。",
    },
]
