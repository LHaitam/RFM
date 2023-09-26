from django.utils import timezone
from django import forms
from .models import Produit, LigneProd, EtatLigne, MouvementTempsReel, ObjectifHebdo



####################################################################################################################
#Produit form 


class ProduitForm(forms.ModelForm):
    class Meta:
        model = Produit
        fields = ['reference', 'nom', 'photo', 'ligne_production']

    def __init__(self, *args, **kwargs):
        super(ProduitForm, self).__init__(*args, **kwargs)
        self.fields['reference'].label = "Référence"
        self.fields['nom'].label = "Nom"
        self.fields['photo'].label = "Photo"
        self.fields['ligne_production'].label = "Ligne de production"
        self.fields['ligne_production'].empty_label = "Sélectionner une ligne de production"
        self.fields['photo'].required = False


####################################################################################################################
#Ligne Production form 


class LigneProductionForm(forms.ModelForm):
    class Meta:
        model = LigneProd
        fields = ('nom', 'etat', 'commentaire')  # Inclure le champ de commentaire dans les champs du formulaire
        labels = {
            'nom': 'Nom',
            'etat': 'État',
            'commentaire': 'Commentaire',  # Libellé du champ de commentaire
        }
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'etat': forms.Select(attrs={'class': 'form-control'}, choices=[('OK', 'OK'), ('KO', 'KO')]),
            'commentaire': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),  # Utiliser un widget Textarea pour le champ de commentaire
        }
    
    def __init__(self, *args, **kwargs):
        super(LigneProductionForm, self).__init__(*args, **kwargs)


####################################################################################################################
#Etat de Ligne Production form 


class EtatLigneForm(forms.ModelForm):
    class Meta:
        model = EtatLigne
        fields = ('ligne_production', 'etat', 'commentaire')
        labels = {
            'ligne_production': 'Ligne de production',
            'etat': 'État de la ligne de production',
            'commentaire': 'Commentaire',
        }
        widgets = {
            'ligne_production': forms.Select(attrs={'class': 'form-control'}),
            'etat': forms.Select(attrs={'class': 'form-control'}),
            'commentaire': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


####################################################################################################################
#Mouvement form 



class MouvementForm(forms.ModelForm):
    class Meta:
        model = MouvementTempsReel
        exclude = ('date_heure', 'numero_semaine')  # Exclure les champs 'date_heure' et 'numero_semaine'
        labels = {
            'quantite': 'Quantité',
            'commentaire': 'Commentaire',
        }
        widgets = {
            'quantite': forms.NumberInput(attrs={'class': 'form-control'}),
            'commentaire': forms.TextInput(attrs={'class': 'form-control'}),
        }


####################################################################################################################
#Objectif Hebdo form 


class ObjectifHebdoForm(forms.ModelForm):
    class Meta:
        model = ObjectifHebdo
        fields = ('produit', 'client', 'date_debut', 'date_fin', 'quantite')
        labels = {
            'produit': 'Produit',
            'client': 'Client',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
            'quantite': 'Quantité hebdomadaire',
        }
        widgets = {
            'produit': forms.Select(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super(ObjectifHebdoForm, self).__init__(*args, **kwargs)
        # Personnaliser le widget du champ 'date_fin'
        self.fields['date_fin'].widget = forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': timezone.now().strftime('%Y-%m-%d'),  # Date minimum : aujourd'hui
        })

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin:
            if date_debut > date_fin:
                self.add_error('date_fin', "La date de fin doit être postérieure à la date de début.")


                