export const flowTemplates = [
    {
        id: 'browser-basic',
        label: 'Browser — mot de passe',
        description: 'Connexion navigateur avec cookie existant et formulaire username/password.',
        flow: {
            alias: 'browser-custom', description: 'Browser flow — cookie et formulaire', topLevel: true, providerId: 'basic-flow', builtIn: false,
            nodes: [
                { nodeId: 'tpl-cookie', type: 'execution', displayName: 'Cookie', providerId: 'auth-cookie', requirement: 'ALTERNATIVE', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'DISABLED'], priority: 10, config: {}, position: { x: 60, y: 80 } },
                { nodeId: 'tpl-forms', type: 'subflow', displayName: 'Forms', providerId: 'basic-flow', alias: 'forms-custom', flowType: 'basic', requirement: 'ALTERNATIVE', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'CONDITIONAL', 'DISABLED'], priority: 20, description: 'Authentification par formulaire', children: [
                        { nodeId: 'tpl-password', type: 'execution', displayName: 'Username Password Form', providerId: 'auth-username-password-form', requirement: 'REQUIRED', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'DISABLED'], priority: 10, config: {}, position: { x: 270, y: 170 } }
                    ], position: { x: 250, y: 100 } }
            ]
        }
    },
    {
        id: 'browser-kerberos-mfa',
        label: 'Browser — Kerberos + OTP conditionnel',
        description: 'Cookie et Kerberos en alternatives, formulaire avec OTP conditionnel.',
        flow: {
            alias: 'browser-kerberos-mfa', description: 'Browser avec SSO Kerberos et OTP conditionnel', topLevel: true, providerId: 'basic-flow', builtIn: false,
            nodes: [
                { nodeId: 'tpl2-cookie', type: 'execution', displayName: 'Cookie', providerId: 'auth-cookie', requirement: 'ALTERNATIVE', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'DISABLED'], priority: 10, config: {}, position: { x: 60, y: 70 } },
                { nodeId: 'tpl2-kerberos', type: 'execution', displayName: 'Kerberos', providerId: 'auth-spnego', requirement: 'ALTERNATIVE', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'DISABLED'], priority: 20, config: {}, position: { x: 60, y: 180 } },
                { nodeId: 'tpl2-forms', type: 'subflow', displayName: 'Forms', providerId: 'basic-flow', alias: 'forms-kerberos-mfa', flowType: 'basic', requirement: 'ALTERNATIVE', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'CONDITIONAL', 'DISABLED'], priority: 30, description: 'Formulaire et MFA', children: [
                        { nodeId: 'tpl2-password', type: 'execution', displayName: 'Username Password Form', providerId: 'auth-username-password-form', requirement: 'REQUIRED', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'DISABLED'], priority: 10, config: {}, position: { x: 270, y: 230 } },
                        { nodeId: 'tpl2-otp-flow', type: 'subflow', displayName: 'Conditional OTP', providerId: 'basic-flow', alias: 'conditional-otp-custom', flowType: 'basic', requirement: 'CONDITIONAL', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'CONDITIONAL', 'DISABLED'], priority: 20, description: 'OTP seulement si l’utilisateur l’a configuré', children: [
                                { nodeId: 'tpl2-otp-condition', type: 'execution', displayName: 'Condition - User Configured', providerId: 'conditional-user-configured', requirement: 'REQUIRED', requirementChoices: ['REQUIRED', 'DISABLED'], priority: 10, config: {}, position: { x: 470, y: 300 } },
                                { nodeId: 'tpl2-otp', type: 'execution', displayName: 'OTP Form', providerId: 'auth-otp-form', requirement: 'REQUIRED', requirementChoices: ['REQUIRED', 'ALTERNATIVE', 'DISABLED'], priority: 20, config: {}, position: { x: 470, y: 400 } }
                            ], position: { x: 260, y: 350 } }
                    ], position: { x: 250, y: 170 } }
            ]
        }
    }
];
