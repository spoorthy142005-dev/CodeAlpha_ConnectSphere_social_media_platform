from django import forms
from .models import Report


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason', 'notes']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={
                'placeholder': 'Provide additional details or context to assist moderators...',
                'rows': 3,
                'class': 'form-control',
                'maxlength': '500',
            }),
        }
        labels = {
            'reason': 'Reason for Reporting',
            'notes': 'Additional Details (Optional)',
        }


class ModerationActionForm(forms.ModelForm):
    delete_content = forms.BooleanField(
        required=False,
        label="Delete target content (Post or Comment) immediately",
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )

    class Meta:
        model = Report
        fields = ['status', 'resolution_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'resolution_notes': forms.Textarea(attrs={
                'placeholder': 'Moderator resolution notes...',
                'rows': 3,
                'class': 'form-control',
            }),
        }
