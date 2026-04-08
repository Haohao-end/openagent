import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
    usePasswordLogin,
    usePrepareRegister,
    useVerifyRegister,
} from '@/hooks/use-auth'
import * as authService from '@/services/auth'

vi.mock('@/services/auth', async () => {
    const actual = await vi.importActual<typeof import('@/services/auth')>('@/services/auth')
    return {
        ...actual,
        passwordLogin: vi.fn(),
        prepareRegister: vi.fn(),
        verifyRegister: vi.fn(),
    }
})

describe('use-auth register flow', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('stores password login authorization after success', async () => {
        vi.mocked(authService.passwordLogin).mockResolvedValue({
            data: { access_token: 'token-1', expire_at: 123 },
        } as never)

        const { loading, authorization, handlePasswordLogin } = usePasswordLogin()
        expect(loading.value).toBe(false)

        await handlePasswordLogin('tester@example.com', 'Abcd1234')

        expect(authService.passwordLogin).toHaveBeenCalledWith('tester@example.com', 'Abcd1234')
        expect(authorization.value).toEqual({ access_token: 'token-1', expire_at: 123 })
        expect(loading.value).toBe(false)
    })

    it('returns prepare-register response and resets loading', async () => {
        vi.mocked(authService.prepareRegister).mockResolvedValue({
            message: '验证码已发送到您的邮箱,请查收',
            data: {},
        } as never)

        const { loading, handlePrepareRegister } = usePrepareRegister()
        const resp = await handlePrepareRegister('tester@example.com', 'Abcd1234')

        expect(authService.prepareRegister).toHaveBeenCalledWith('tester@example.com', 'Abcd1234')
        expect(resp).toEqual({
            message: '验证码已发送到您的邮箱,请查收',
            data: {},
        })
        expect(loading.value).toBe(false)
    })

    it('stores register authorization after verify success', async () => {
        vi.mocked(authService.verifyRegister).mockResolvedValue({
            data: { access_token: 'token-2', expire_at: 456 },
        } as never)

        const { loading, authorization, handleVerifyRegister } = useVerifyRegister()
        await handleVerifyRegister('tester@example.com', 'Abcd1234', '123456')

        expect(authService.verifyRegister).toHaveBeenCalledWith(
            'tester@example.com',
            'Abcd1234',
            '123456',
        )
        expect(authorization.value).toEqual({ access_token: 'token-2', expire_at: 456 })
        expect(loading.value).toBe(false)
    })
})
