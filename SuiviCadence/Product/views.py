import json
import math
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import EtatLigne, LigneProd, Produit, ObjectifHebdo, MouvementTempsReel, Realisation
from datetime import datetime, timedelta
from django.db.models import Sum, Q, OuterRef, Subquery
from .forms import EtatLigneForm, LigneProductionForm, MouvementForm, ObjectifHebdoForm, ProduitForm
from django.http import Http404, HttpRequest
from django.utils import timezone
import pytz

# Create your views here.


####################################################################################################################
# Vue du Produit 


def produit(request, produit_id):
    try:
        produit = get_object_or_404(Produit, pk=produit_id)
        date = datetime.now()
        now = timezone.localtime()

        # Récupérer l'objectif hebdomadaire courant du produit
        dernier_objectif_hebdo = ObjectifHebdo.objects.filter(produit=produit).first()

        # Si aucun objectif hebdomadaire n'existe pour le produit cette semaine, créer un nouvel objectif
        if not dernier_objectif_hebdo:
            debut_semaine = date - timedelta(days=date.weekday())
            fin_semaine = debut_semaine + timedelta(days=4)

            dernier_objectif_hebdo = ObjectifHebdo.objects.create(
                produit=produit,
                numero_semaine=date.isocalendar()[1],
                date_debut=debut_semaine,
                date_fin=fin_semaine,
                quantite=0
            )


        # Calculer le takt théorique
        jours_travailles = 5  # Nombre de jours de travail par semaine
        heures_travailles = 8  # Nombre d'heures de travail par jour
        if dernier_objectif_hebdo.quantite == 0 or dernier_objectif_hebdo.quantite is None:
            takt_theorique = 0
        else:
            takt_theorique = math.floor(float(dernier_objectif_hebdo.quantite / (jours_travailles * heures_travailles)) * 10) / 10

        # Définition des jours de la semaine
        debut_semaine = date - timedelta(days=date.weekday())
        lundi = debut_semaine
        mardi = debut_semaine + timedelta(days=1)
        mercredi = debut_semaine + timedelta(days=2)
        jeudi = debut_semaine + timedelta(days=3)
        vendredi = debut_semaine + timedelta(days=4)

        # Définition des cibles horaires par jour
        cible_horaire = takt_theorique
        heures_cibles_jour = [
            {'datetime__hour': 8, 'total_ach': 0},
            {'datetime__hour': 9, 'total_ach': cible_horaire * 1},
            {'datetime__hour': 10, 'total_ach': cible_horaire * 2},
            {'datetime__hour': 11, 'total_ach': cible_horaire * 3},
            {'datetime__hour': 12, 'total_ach': cible_horaire * 4},
            {'datetime__hour': 13, 'total_ach': cible_horaire * 5},
            {'datetime__hour': 14, 'total_ach': cible_horaire * 6},
            {'datetime__hour': 15, 'total_ach': cible_horaire * 7},
            {'datetime__hour': 16, 'total_ach': cible_horaire * 8},
            {'datetime__hour': 17, 'total_ach': cible_horaire * 9},
            {'datetime__hour': 18, 'total_ach': cible_horaire * 10},
        ]

        # Définition des cibles journalières par jour
        cible_journaliere = math.floor(float(dernier_objectif_hebdo.quantite / jours_travailles) * 10) / 10
        cibles_journalieres = [
            {'datetime__date': lundi.date(), 'total_ach': cible_journaliere},
            {'datetime__date': mardi.date(), 'total_ach': cible_journaliere},
            {'datetime__date': mercredi.date(), 'total_ach': cible_journaliere},
            {'datetime__date': jeudi.date(), 'total_ach': cible_journaliere},
            {'datetime__date': vendredi.date(), 'total_ach': cible_journaliere},
        ]

        # Calcul du total des réalisations par jour
        debut_semaine = date - timedelta(days=date.weekday())
        fin_semaine = debut_semaine + timedelta(days=4)
        mouvements_par_jour = MouvementTempsReel.objects.filter(produit=produit, date_heure__date__range=(debut_semaine, fin_semaine)).values('date_heure__date').annotate(total_ach=Sum('quantite'))

        # Calcul du takt réel
        total_realise = mouvements_par_jour.aggregate(Sum('total_ach'))['total_ach__sum']
        if total_realise is None or total_realise == 0:
            takt_reel = 0
        else:
            takt_reel = math.floor(float(total_realise / (date.hour - 8)) * 10) / 10 if date.hour > 8 else 0

        # Calcul de la progression théorique et du retard
        progression_theorique = math.floor(float(takt_theorique * (date.hour - 8)) * 10) / 10 if date.hour >= 8 else 0
        if total_realise is None:
            retard = progression_theorique
        else:
            retard = math.floor(float(progression_theorique - total_realise) * 10) / 10

        # Calcul du total des mouvements jusqu'à présent aujourd'hui
        mouvements_jusqua_present = MouvementTempsReel.objects.filter(Q(date_heure__date=date) & Q(date_heure__time__lte=date), produit=produit).annotate(total_ach=Sum('quantite'))
        total_mouvements_aujourdhui = mouvements_jusqua_present.aggregate(Sum('total_ach'))['total_ach__sum']

        # Calcul du reste à faire
        if dernier_objectif_hebdo.quantite is not None and total_realise is not None:
            reste_a_faire = math.floor(float(dernier_objectif_hebdo.quantite - total_realise) * 10) / 10
        else:
            # Gérer le cas où l'une des variables est None
            reste_a_faire = 0  # Ou une autre valeur par défaut selon votre logique

        # Récupérer l'objectif hebdomadaire de la semaine courante

        objectif_semaine_courante = ObjectifHebdo.objects.filter(
            produit=produit,
            numero_semaine=date.isocalendar()[1]
        ).last()

        # Récupérer les mouvements du produit par heure pour le jour courant

        mouvements_par_heure = MouvementTempsReel.objects.filter(
            produit=produit, 
            date_heure__date=now.date()
        ).values('date_heure').annotate(total_ach=Sum('quantite'))


        # Formatage des données mouvements_par_heure dans un format utilisable par le graphique

        # Supposons que mouvements_par_heure est votre ValuesQuerySet

        # Créez une nouvelle liste pour stocker les valeurs mises à jour
        mouvements_format = []

        # Itérez sur les éléments du ValuesQuerySet
        for mouvement in mouvements_par_heure:
            heure = mouvement['date_heure'] + timedelta(hours=1)
            quantite = mouvement['total_ach']
            mouvements_format.append([heure.strftime('%H:%M'), quantite])

        # Convertir les données en format JSON
        mouvements_json = json.dumps(mouvements_format)
        

        mouvements_format_jour = [
            {'date_heure__date': mouvement['date_heure__date'].strftime('%Y-%m-%d'), 'total_ach': mouvement['total_ach']}
            for mouvement in mouvements_par_jour
        ]

        mouvements_json_jour = json.dumps(mouvements_format_jour)

        numero_semaine_en_cours = date.isocalendar()[1]


        context = {
            'date': date,
            'produit': produit,
            'numero_semaine': numero_semaine_en_cours,
            'debut_semaine': dernier_objectif_hebdo.date_debut,
            'fin_semaine': dernier_objectif_hebdo.date_fin,
            'objectif_hebdo': dernier_objectif_hebdo,
            'objectif_semaine_courante':objectif_semaine_courante,
            'takt_theorique': takt_theorique,
            'takt_reel': takt_reel,
            'progression_theorique': progression_theorique,
            'retard': retard,
            'total_realise': total_realise,
            'reste_a_faire': reste_a_faire,
            'cibles_heures_jour': heures_cibles_jour,
            'cibles_journalieres': cibles_journalieres,
            'mouvements_par_jour': mouvements_json_jour,
            'total_mouvements_aujourdhui': total_mouvements_aujourdhui,
            'mouvements_par_heure': mouvements_json,
        }

        return render(request, 'produit.html', context)

    except Produit.DoesNotExist:
        # Gérer l'exception si le produit n'existe pas
        return render(request, 'produit_inexistant.html')

####################################################################################################################
#Vue Liste des Produits


def liste_produits(request):
    # Récupérer tous les produits de la base de données
    produits = Produit.objects.all()

    # Calculer le takt_theo en dehors de la boucle pour les produits
    try:
        objectif_hebdo = ObjectifHebdo.objects.first()
        if objectif_hebdo:
            takt_theo = math.floor(float(objectif_hebdo.quantite / (5 * 8)) * 10) / 10
        else:
            takt_theo = 0
    except:
        takt_theo = 0

    # Préparer le contexte pour le rendu du template avec la liste des produits et le takt_theo
    context = {
        "produits": produits,
        "titre": "Liste des produits",
        "takt_theo": takt_theo,
    }

    # Rendre le template avec la liste des produits et le contexte
    return render(request, 'liste_produits.html', context)


####################################################################################################################
#Vue pour ajouter Produit


def ajouter_produit(request):
    if request.method == "POST":
        form = ProduitForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Le produit a été ajouté avec succès.")
            return redirect('liste_produits')
        else:
            messages.error(request, "Erreur lors de l'ajout du produit. Veuillez vérifier les données saisies.")
    else:
        form = ProduitForm()

    context = {
        "form": form,
        "titre": "Ajouter un produit",
    }

    return render(request, 'ajouter_produit.html', context)



####################################################################################################################
#Vue pour modifier Produit


def modifier_produit(request, produit_id):
    # Récupérer le produit existant à partir de son ID
    produit = get_object_or_404(Produit, id=produit_id)

    if request.method == "POST":
        # Créer une instance du formulaire avec les données POST et les fichiers téléchargés, le cas échéant
        form = ProduitForm(request.POST, request.FILES, instance=produit)
        # Vérifier si le formulaire est valide
        if form.is_valid():
            # Sauvegarder les modifications du produit dans la base de données sans les commettre immédiatement
            produit = form.save(commit=False)
            # Enregistrer les modifications du produit dans la base de données
            produit.save()
            # Afficher un message de succès à l'utilisateur
            messages.success(request, "Le produit a été modifié avec succès.")
            # Rediriger l'utilisateur vers une vue de confirmation ou une autre page appropriée
            return redirect('liste_produits')
        else:
            # Si le formulaire n'est pas valide, afficher un message d'erreur
            messages.error(request, "Erreur lors de la modification du produit. Veuillez vérifier les données saisies.")
    else:
        # Si la requête n'est pas de type POST, créer une instance du formulaire avec les données du produit existant
        form = ProduitForm(instance=produit)

    # Préparer le contexte pour le rendu du template avec le formulaire
    context = {
        "form": form,
        "titre": "Modifier le produit",
    }

    # Rendre le template avec le formulaire et le contexte
    return render(request, 'modifier_produit.html', context)


####################################################################################################################
#Vue pour modifier Produit


def supprimer_produit(request, pk):
    # Récupérer le produit existant en fonction de la clé primaire (pk) passée dans l'URL
    produit = get_object_or_404(Produit, pk=pk)

    if request.method == "POST":
        # Supprimer le produit de la base de données
        produit.delete()
        # Afficher un message de succès à l'utilisateur
        messages.success(request, "Le produit a été supprimé avec succès.")
        # Rediriger l'utilisateur vers une vue de confirmation ou une autre page appropriée
        return redirect('liste_produits')

    # Préparer le contexte pour le rendu du template avec le produit à supprimer
    context = {
        "produit": produit,
        "titre": "Supprimer le produit",
    }

    # Rendre le template de confirmation de suppression avec le contexte
    return render(request, 'supprimer_produit.html', context)



####################################################################################################################

####################################################################################################################
#Vue Ligne de Production 


def details_ligne_production(request, ligne_production_id):
    ligne_production = get_object_or_404(LigneProd, id=ligne_production_id)
    dernier_etat = EtatLigne.objects.filter(ligne_production=ligne_production).last()
    produits = Produit.objects.filter(ligne_production=ligne_production)

    liste_produits = []
    date = datetime.now()
    numero_semaine = date.isocalendar()[1]
    debut_semaine = date - timedelta(days=date.weekday())
    fin_semaine = debut_semaine + timedelta(days=4)

    for produit in produits:
        dernier_objectif_hebdo, created = ObjectifHebdo.objects.get_or_create(
            produit=produit,
            numero_semaine=numero_semaine,
            defaults={
                'date_debut': debut_semaine,
                'date_fin': fin_semaine,
                'quantite': 0,
            }
        )

        jours_travailles = 5
        heures_travailles = 8
        if dernier_objectif_hebdo.quantite == 0 or dernier_objectif_hebdo.quantite is None:
            takt_theorique = 0
        else:
            takt_theorique = math.floor(float(dernier_objectif_hebdo.quantite / (jours_travailles * heures_travailles)) * 10) / 10

        lundi = debut_semaine
        mardi = debut_semaine + timedelta(days=1)
        mercredi = debut_semaine + timedelta(days=2)
        jeudi = debut_semaine + timedelta(days=3)
        vendredi = debut_semaine + timedelta(days=4)

        cibles_heures_jour = [
            {'datetime__hour': 8, 'total_ach': 0},
            {'datetime__hour': 9, 'total_ach': takt_theorique * 1},
            {'datetime__hour': 10, 'total_ach': takt_theorique * 2},
            {'datetime__hour': 11, 'total_ach': takt_theorique * 3},
            {'datetime__hour': 14, 'total_ach': takt_theorique * 4},
            {'datetime__hour': 15, 'total_ach': takt_theorique * 5},
            {'datetime__hour': 16, 'total_ach': takt_theorique * 6},
            {'datetime__hour': 17, 'total_ach': takt_theorique * 7},
        ]

        cibles_journalieres = [
            {'datetime__date': lundi.date(), 'total_ach': math.floor(float(dernier_objectif_hebdo.quantite / jours_travailles) * 10) / 10},
            {'datetime__date': mardi.date(), 'total_ach': math.floor(float(dernier_objectif_hebdo.quantite / jours_travailles) * 2 * 10) / 10},
            {'datetime__date': mercredi.date(), 'total_ach': math.floor(float(dernier_objectif_hebdo.quantite / jours_travailles) * 3 * 10) / 10},
            {'datetime__date': jeudi.date(), 'total_ach': math.floor(float(dernier_objectif_hebdo.quantite / jours_travailles) * 4 * 10) / 10},
            {'datetime__date': vendredi.date(), 'total_ach': math.floor(float(dernier_objectif_hebdo.quantite / jours_travailles) * 5 * 10) / 10},
        ]

        mouvements_par_jour = MouvementTempsReel.objects.filter(produit=produit, date_heure__date__range=(debut_semaine, fin_semaine)).values('date_heure__date').annotate(total_ach=Sum('quantite'))

        total_realise = mouvements_par_jour.aggregate(Sum('total_ach'))['total_ach__sum']
        if total_realise is None or total_realise == 0:
            takt_reel = 0
        else:
            takt_reel = math.floor(float(total_realise / (date.hour - 8)) * 10) / 10 if date.hour > 8 else 0

        progression_theorique = math.floor(float(takt_theorique * (date.hour - 8)) * 10) / 10 if date.hour >= 8 else 0
        if total_realise is None:
            retard = progression_theorique
        else:
            retard = math.floor(float(progression_theorique - total_realise) * 10) / 10

        mouvements_jusqua_present = MouvementTempsReel.objects.filter(Q(date_heure__date=date) & Q(date_heure__time__lte=date), produit=produit).annotate(total_ach=Sum('quantite'))
        total_mouvements_aujourdhui = mouvements_jusqua_present.aggregate(Sum('total_ach'))['total_ach__sum']

        reste_a_faire = math.floor(float(dernier_objectif_hebdo.quantite - progression_theorique) * 10) / 10

        objectif_semaine_courante = ObjectifHebdo.objects.filter(produit=produit, numero_semaine=date.isocalendar()[1]).first()

        mouvements_par_heure = MouvementTempsReel.objects.filter(
            produit=produit, 
            date_heure__date=date.date()
            ).values('date_heure__hour').annotate(total_ach=Sum('quantite'))
        mouvements_format = [(mouvement['date_heure__hour'], mouvement['total_ach']) for mouvement in mouvements_par_heure]

        liste_produits.append(
            {
                'produit': produit,
                'numero_semaine': dernier_objectif_hebdo.numero_semaine,
                'debut_semaine': dernier_objectif_hebdo.date_debut,
                'fin_semaine': dernier_objectif_hebdo.date_fin,
                'objectif_hebdo': dernier_objectif_hebdo,
                'takt_theorique': takt_theorique,
                'takt_reel': takt_reel,
                'progression_theorique': progression_theorique,
                'retard': retard,
                'total_realise': total_realise,
                'reste_a_faire': reste_a_faire,
                'cibles_heures_jour': cibles_heures_jour,
                'cibles_journalieres': cibles_journalieres,
                'mouvements_par_jour': mouvements_par_jour,
                'total_mouvements_aujourdhui': total_mouvements_aujourdhui,
                'mouvements_par_heure': mouvements_format,
            }
        )

    context = {
        'ligne_production': ligne_production,
        'dernier_etat': dernier_etat,
        'produits': liste_produits,
        'titre': 'Détails de la ligne de production',
        'numero_semaine': numero_semaine,
    }

    return render(request, 'ligne_production.html', context)


####################################################################################################################
#Vue liste Ligne de Production 


def liste_lignes_production(request):
    # Récupérer toutes les lignes de production de la base de données
    lignes_production = LigneProd.objects.all()

    # Préparer le contexte pour le rendu du template avec la liste des lignes de production
    context = {
        'lignes_production': lignes_production,
        'titre': 'Liste des lignes de production',
    }

    # Rendre le template avec le contexte
    return render(request, 'liste_lignes_production.html', context)


####################################################################################################################
#Vue pour ajouter Ligne de Production 


def ajouter_ligne_production(request):
    try:
        if request.method == 'POST':
            form = LigneProductionForm(request.POST)
            if form.is_valid():
                ligne_production = form.save()
                return redirect('details_ligne_production', ligne_production_id=ligne_production.pk)
        else:
            form = LigneProductionForm()
        
        context = {
            'form': form,
            'titre': 'Ajouter ligne de production',
        }
        
        return render(request, 'ajouter_ligne_production.html', context)
    
    except Exception as e:
        # En cas d'erreur, vous pouvez ajouter un message d'erreur à votre contexte pour l'afficher dans le template
        context['erreur'] = f"Une erreur s'est produite : {str(e)}"
        return render(request, 'ajouter_ligne_production.html', context)


####################################################################################################################
#Vue pour modifier Ligne de Production 


def modifier_ligne_production(request, pk):
    try:
        # Récupérer la ligne de production existante en fonction de la clé primaire (pk) passée dans l'URL
        ligne_production = get_object_or_404(LigneProd, pk=pk)

        # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire a été soumis
        if request.method == 'POST':
            # Créer une instance du formulaire avec les données POST soumises par l'utilisateur
            form = LigneProductionForm(request.POST, instance=ligne_production)
            # Vérifier si le formulaire est valide
            if form.is_valid():
                # Sauvegarder les modifications de la ligne de production dans la base de données
                form.save()
                # Rediriger l'utilisateur vers la liste des lignes de production actualisée
                return redirect('liste_lignes_production')
        else:
            # Si la requête n'est pas de type POST, créer une instance du formulaire avec les données de la ligne de production existante
            form = LigneProductionForm(instance=ligne_production)

        # Préparer le contexte pour le rendu du template avec le formulaire et la ligne de production existante
        context = {
            'form': form,
            'ligne_production': ligne_production,
            'titre': 'Modifier la ligne de production',
        }

        # Rendre le template avec le formulaire et le contexte
        return render(request, 'modifier_ligne_production.html', context)
    
    except Exception as e:
        # Gérer toutes les autres exceptions non spécifiées ci-dessus
        # Par exemple, si une erreur de base de données se produit, une erreur 500 sera renvoyée
        # Vous pouvez personnaliser la gestion des exceptions ici en fonction de vos besoins
        raise Http404("Une erreur s'est produite lors de la modification de la ligne de production.")


####################################################################################################################
#Vue pour supprimer Ligne de Production


def supprimer_ligne_production(request, pk):

        # Récupérer la ligne de production existante en fonction de la clé primaire (pk) passée dans l'URL
        ligne_production = get_object_or_404(LigneProd, pk=pk)

        # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire a été soumis
        if request.method == 'POST':
            # Supprimer la ligne de production de la base de données
            ligne_production.delete()
            # Rediriger l'utilisateur vers une vue appropriée (par exemple, la liste des lignes de production)
            return redirect('liste_lignes_production')  # Correction de l'URL ici

        # Préparer le contexte pour le rendu du template avec la ligne de production
        context = {
            'ligne_production': ligne_production,
            'titre': 'Supprimer la ligne de production',
        }

        # Rendre le template de confirmation de suppression avec le contexte
        return render(request, 'supprimer_ligne_production.html', context)  # Correction du nom du template ici


####################################################################################################################
#Vue pour modifier l'Etat de Ligne 


def modifier_etat_ligne(request, pk):
    try:
        # Récupérer l'état de la ligne de production existante en fonction de la clé primaire (pk) passée dans l'URL
        etat_ligne = get_object_or_404(EtatLigne, pk=pk)

        # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire a été soumis
        if request.method == 'POST':
            # Créer une instance du formulaire avec les données POST soumises par l'utilisateur
            form = EtatLigneForm(request.POST, instance=etat_ligne)
            # Vérifier si le formulaire est valide
            if form.is_valid():
                # Sauvegarder les modifications de l'état de la ligne de production dans la base de données
                form.save()
                # Rediriger l'utilisateur vers une vue appropriée (par exemple, la liste des lignes de production)
                return redirect('nom_de_la_vue_appropriee')

        else:
            # Si la requête n'est pas de type POST, créer une instance du formulaire avec les données de l'état de la ligne existante
            form = EtatLigneForm(instance=etat_ligne)

        # Préparer le contexte pour le rendu du template avec le formulaire
        context = {
            'form': form,
            'titre': 'Modifier l\'état de la ligne de production',
        }

        # Rendre le template avec le formulaire et le contexte
        return render(request, 'modifier_etat_ligne.html', context)

    except Exception as e:
        # Gérer toutes les autres exceptions non spécifiées ci-dessus
        # Par exemple, si une erreur de base de données se produit, une erreur 500 sera renvoyée
        # Vous pouvez personnaliser la gestion des exceptions ici en fonction de vos besoins
        raise Http404("Une erreur s'est produite lors de la modification de l'état de la ligne de production.")


####################################################################################################################

####################################################################################################################
#Vue pour lister Mouvement


def liste_mouvements(request):
    # Récupérer les mouvements triés par date_heure (du plus récent au plus ancien)
    mouvements = MouvementTempsReel.objects.all().order_by('-date_heure')

    context = {
        'mouvements': mouvements
    }

    return render(request, 'liste_mouvements.html', context)    # Récupérer tous les mouvements de la base de données



####################################################################################################################
#Vue pour ajouter Mouvement


def ajouter_mouvement(request):
    if request.method == "POST":
        form = MouvementForm(request.POST)
        if form.is_valid():
            # Obtenir la date et l'heure actuelles
            date_heure_actuelles = datetime.now()
            # Définir la date et l'heure actuelles dans le champ date_heure
            form.instance.date_heure = date_heure_actuelles
            # Sauvegarder le formulaire avec les données automatiques
            form.save()
            return redirect('liste_mouvements')
    else:
        form = MouvementForm()

    context = {
        'form': form,
    }

    return render(request, 'ajouter_mouvement.html', context)


####################################################################################################################
#Vue pour modifier Mouvement


def modifier_mouvement(request, mouvement_id):
    mouvement = get_object_or_404(MouvementTempsReel, id=mouvement_id)

    if request.method == 'POST':
        form = MouvementForm(request.POST, instance=mouvement)
        if form.is_valid():
            mouvement = form.save()
            return redirect('liste_mouvements')
    else:
        form = MouvementForm(instance=mouvement)

    context = {
        'form': form
    }
    return render(request, 'modifier_mouvement.html', context)


####################################################################################################################
#Vue pour supprimer Mouvement

def supprimer_mouvement(request, mouvement_id):
    mouvement = get_object_or_404(MouvementTempsReel, pk=mouvement_id)

    # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire de confirmation a été soumis
    if request.method == 'POST':
        # Supprimer le mouvement de la base de données
        mouvement.delete()
        # Rediriger l'utilisateur vers une autre page après la suppression réussie
        return redirect('liste_mouvements')

    context = {
        'mouvement': mouvement
    }
    return render(request, 'supprimer_mouvement.html', context)


####################################################################################################################

####################################################################################################################
#Vue pour lister Objectif Hebdo


def liste_objectifs_hebdo(request):
    # Récupérer tous les objectifs hebdomadaires de la base de données
    objectifs = ObjectifHebdo.objects.all().order_by('-date_debut')

    # Préparer le contexte pour le rendu du template avec la liste des objectifs
    context = {
        'objectifs': objectifs,
    }

    # Rendre le template avec la liste des objectifs et le contexte
    return render(request, 'liste_objectifs_hebdo.html', context)

####################################################################################################################
#Vue pour ajouter Objectif Hebdo


def ajouter_objectif_hebdo(request):
    try:
        # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire a été soumis
        if request.method == 'POST':
            # Créer une instance du formulaire avec les données POST soumises par l'utilisateur
            form = ObjectifHebdoForm(request.POST)
            # Vérifier si le formulaire est valide
            if form.is_valid():
                # Sauvegarder le nouvel objectif hebdomadaire dans la base de données
                objectif_hebdo = form.save()
                # Rediriger l'utilisateur vers la page de détails du nouvel objectif hebdomadaire
                return redirect('liste_objectifs_hebdo')

        else:
            # Si la requête n'est pas de type POST, créer une instance vide du formulaire
            form = ObjectifHebdoForm()

        # Préparer le contexte pour le rendu du template avec le formulaire
        context = {
            'form': form,
            'titre': 'Ajouter un nouvel objectif hebdomadaire',
        }

        # Rendre le template avec le formulaire et le contexte
        return render(request, 'ajouter_objectif_hebdo.html', context)

    except Exception as e:
        # Gérer toutes les autres exceptions non spécifiées ci-dessus
        # Par exemple, si une erreur de base de données se produit, une erreur 500 sera renvoyée
        # Vous pouvez personnaliser la gestion des exceptions ici en fonction de vos besoins
        raise Http404("Une erreur s'est produite lors de l'ajout de l'objectif hebdomadaire.")


####################################################################################################################
#Vue pour modifier Objectif Hebdo


def modifier_objectif_hebdo(request, pk):
    try:
        # Récupérer l'objectif hebdomadaire existant en fonction de la clé primaire (pk) passée dans l'URL
        objectif_hebdo = get_object_or_404(ObjectifHebdo, pk=pk)

        # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire a été soumis
        if request.method == 'POST':
            # Créer une instance du formulaire avec les données POST soumises par l'utilisateur
            form = ObjectifHebdoForm(request.POST, instance=objectif_hebdo)
            # Vérifier si le formulaire est valide
            if form.is_valid():
                # Sauvegarder les modifications de l'objectif hebdomadaire dans la base de données
                form.save()
                # Rediriger l'utilisateur vers la page de détails de l'objectif hebdomadaire modifié
                return redirect('liste_objectifs_hebdo')

        else:
            # Si la requête n'est pas de type POST, créer une instance du formulaire avec les données de l'objectif hebdomadaire existant
            form = ObjectifHebdoForm(instance=objectif_hebdo)

        # Préparer le contexte pour le rendu du template avec le formulaire et l'objectif hebdomadaire existant
        context = {
            'form': form,
            'titre': 'Modifier l\'objectif hebdomadaire',
            'objectif_hebdo': objectif_hebdo,
        }

        # Rendre le template avec le formulaire et le contexte
        return render(request, 'modifier_objectif_hebdo.html', context)

    except Exception as e:
        # Gérer toutes les autres exceptions non spécifiées ci-dessus
        # Par exemple, si une erreur de base de données se produit, une erreur 500 sera renvoyée
        # Vous pouvez personnaliser la gestion des exceptions ici en fonction de vos besoins
        raise Http404("Une erreur s'est produite lors de la modification de l'objectif hebdomadaire.")


####################################################################################################################
#Vue pour supprimer Objectif Hebdo


def supprimer_objectif_hebdo(request, objectif_hebdo_id):
    objectif_hebdo = get_object_or_404(ObjectifHebdo, pk=objectif_hebdo_id)

    # Vérifier si la requête est de type POST, c'est-à-dire si le formulaire de confirmation a été soumis
    if request.method == 'POST':
        # Supprimer l'objectif hebdomadaire de la base de données
        objectif_hebdo.delete()
        # Rediriger l'utilisateur vers une autre page après la suppression réussie
        return redirect('liste_objectifs_hebdo')

    context = {
        'objectif_hebdo': objectif_hebdo
    }
    return render(request, 'supprimer_objectif_hebdo.html', context)




####################################################################################################################
#Vue pour tableau_realisation_cumulee


def tableau_realisation_cumulee(request):

    # Récupérer tous les produits
    produits = Produit.objects.all()

    # Créez une liste de nombres de 1 à 52
    weeks = list(range(1, 53))

    # Récupérer les réalisations cumulées pour chaque produit et numéro de semaine
    realisations = Realisation.objects.values('produit__nom', 'numero_semaine').annotate(
        quantite_cumulee=Sum('quantite_cumulee')
    )

    # Créer un dictionnaire pour stocker les données du tableau
    tableau_data = {}

    for produit in produits:
        tableau_data[produit.nom] = [None] * 52  # Initialiser avec None pour chaque semaine

    for realisation in realisations:
        produit_nom = realisation['produit__nom']
        numero_semaine = realisation['numero_semaine']
        quantite_cumulee = realisation['quantite_cumulee']

        # Remplacer None par la quantité cumulée s'il existe
        tableau_data[produit_nom][numero_semaine - 1] = quantite_cumulee

    return render(request, 'tableau_realisation_cumulee.html', {'tableau_data': tableau_data, 'weeks': weeks})

