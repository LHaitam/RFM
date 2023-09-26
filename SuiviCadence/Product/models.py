from datetime import datetime
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Sum
from django.db.models.signals import post_save, post_delete

# Create your models here.


##########################################################################################################################################################
# Modèle LigneProd pour représenter les lignes de production de l'usine

    
class LigneProd(models.Model):
    nom = models.CharField(max_length=100)
    etat = models.CharField(max_length=2, choices=[('OK', 'OK'), ('KO', 'KO')])  # L'état de la ligne de production (OK ou KO)
    commentaire = models.CharField(max_length=300, null=True,)  # Un commentaire sur l'état de la ligne de production

    def save(self, *args, **kwargs):
        # Vérifier si la ligne de production existe déjà en base de données
        is_new_line = self.pk is None

        # Appeler la méthode save() d'origine pour sauvegarder la ligne de production
        super().save(*args, **kwargs)

        # Enregistrer l'état de la ligne dans la table EtatLigne
        if is_new_line:
            # Si c'est une nouvelle ligne de production, créer un nouvel état avec l'état initial "OK" et le commentaire "Création de la ligne"
            EtatLigne.objects.create(ligne_production=self, etat='OK', commentaire='Création de la ligne')
        else:
            # Si la ligne de production existe déjà, créer un nouvel état avec l'état modifié et le commentaire "Modification de l'état"
            EtatLigne.objects.create(ligne_production=self, etat=self.etat, commentaire='Modification de l\'état')
    
    def __str__(self):
        return f"{self.nom} - État : {self.etat} - Commentaire : {self.commentaire}"
    

##########################################################################################################################################################
# Modèle Produit pour représenter les produits fabriqués dans l'usine


def upload_to(instance, filename):
    return f'images/produits/{filename}'

class Produit(models.Model):
    reference = models.CharField(max_length=100)  # La référence du produit
    nom = models.CharField(max_length=200)  # Le nom du produit
    photo = models.ImageField(upload_to=upload_to, null=True, blank=True)  # La photo du produit (optionnelle)
    ligne_production = models.ForeignKey(LigneProd, on_delete=models.CASCADE, related_name='produits')  # La ligne de production à laquelle le produit est associé

    def __str__(self):
        return f"{self.nom} - Référence : {self.reference} - Ligne : {self.ligne_production.nom}"


##########################################################################################################################################################
# Modèle ObjectifHebdo pour représenter les objectifs hebdomadaires de production

class ObjectifHebdo(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    numero_semaine = models.IntegerField(default=1)  # Ajouter une valeur par défaut ici
    choix_clients = (
        ("Airbus", "Airbus"),
        ("Boeing", "Boeing"),
        ("Comac", "Comac"),
    )
    client = models.CharField(choices=choix_clients, max_length=30)
    date_debut = models.DateField()
    date_fin = models.DateField()
    quantite = models.IntegerField()
    utilisateur = models.ForeignKey(User, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.produit.nom} - Client : {self.client}"


##########################################################################################################################################################    
# Modèle Realisation pour représenter les réalisations de production

class Realisation(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    numero_semaine = models.PositiveIntegerField()  # Numéro de la semaine
    quantite_cumulee = models.IntegerField()  # La quantité cumulée produite pour cette semaine (champ entier)
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, null=True)  # L'utilisateur qui a enregistré la réalisation, champ optionnel

    def save(self, *args, **kwargs):
        # Récupérez le numéro de la semaine actuelle
        current_week = datetime.now().isocalendar()[1]

        # Si le numéro de semaine de la réalisation correspond à la semaine actuelle, calculez la quantité cumulée
        if self.numero_semaine == current_week:
            mouvements_semaine = MouvementTempsReel.objects.filter(
                produit=self.produit,
                numero_semaine=current_week
            ).aggregate(Sum('quantite'))

            self.quantite_cumulee = mouvements_semaine['quantite__sum'] or 0  # Assurez-vous que la valeur est au moins 0

        super().save(*args, **kwargs)


##########################################################################################################################################################
# Modèle MouvementTempsReel pour représenter les mouvements de production en temps réel

# Modèle MouvementTempsReel pour représenter les mouvements de production en temps réel
class MouvementTempsReel(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    date_heure = models.DateTimeField(auto_now_add=True)
    quantite = models.IntegerField()
    utilisateur = models.ForeignKey(User, default=1, on_delete=models.CASCADE)
    numero_semaine = models.PositiveIntegerField()  # Numéro de la semaine

    def save(self, *args, **kwargs):
        # Récupérez le numéro de la semaine actuelle
        current_week = datetime.now().isocalendar()[1]
        self.numero_semaine = current_week

        super().save(*args, **kwargs)

@receiver(post_save, sender=MouvementTempsReel)
def update_quantite_cumulee_on_save(sender, instance, **kwargs):
    # Récupérez le numéro de la semaine actuelle
    current_week = datetime.now().isocalendar()[1]

    # Mettez à jour la quantité cumulée
    realisation, created = Realisation.objects.get_or_create(
        produit=instance.produit,
        numero_semaine=current_week
    )

    realisation.quantite_cumulee += instance.quantite
    realisation.save()

@receiver(post_delete, sender=MouvementTempsReel)
def update_quantite_cumulee_on_delete(sender, instance, **kwargs):
    # Récupérez le numéro de la semaine actuelle
    current_week = datetime.now().isocalendar()[1]

    # Mettez à jour la quantité cumulée
    realisation = Realisation.objects.filter(
        produit=instance.produit,
        numero_semaine=current_week
    ).first()

    if realisation:
        realisation.quantite_cumulee -= instance.quantite
        realisation.save()

##########################################################################################################################################################
# Modèle EtatLigne pour représenter les états des lignes de production

class EtatLigne(models.Model):
    ligne_production = models.ForeignKey(LigneProd, on_delete=models.CASCADE)  # La ligne de production associée à l'état
    commentaire = models.CharField(max_length=300)  # Un commentaire sur l'état de la ligne de production
    date_heure = models.DateTimeField(auto_now_add=True)  # La date et l'heure de l'enregistrement de l'état
    utilisateur = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    CHOICES_ETAT = (
        ('OK', 'OK'),
        ('KO', 'KO'),
    )
    etat = models.CharField(max_length=2, choices=CHOICES_ETAT, default='OK')

    def __str__(self):
        formatted_date = self.date_heure.strftime('%d/%m/%y %H:%M:%S')
        return f"État de {self.ligne_production.nom} - État : {self.etat} - Commentaire : {self.commentaire} - Date et heure : {formatted_date}"


